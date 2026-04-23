"""GraphRAG Q&A.

Strategy:
  1. Load the document's structured extraction (15 categories).
  2. Run a *graph-side* query (Cypher) against Neo4j to surface facts that
     live in edges rather than text — e.g. which sections mention which
     standards, which sections cross-reference which appendices/tables.
  3. Compose a compact context containing both, ask the LLM to answer with
     page citations, forced via JSON schema.

This is deliberately *not* Text-to-Cypher — the LLM never writes Cypher.
Instead we pre-run high-value queries and inject the rows as structured
context, which is both safer and more deterministic for a demo.
"""

import textwrap
from typing import Any

from pydantic import BaseModel, Field

from src.core.storage import load as load_extraction
from src.graph.client import Neo4jClient
from src.llm.base import LLMClient, Message


class Citation(BaseModel):
    description: str
    category: str         # items/standards/toxic_clauses/references/...
    page: int | None = None


class ChatAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    used_graph_facts: int = 0


_SYSTEM_PROMPT = textwrap.dedent(
    """\
    You are an expert engineering-document analyst for 코리아스틸, a Korean
    steel manufacturer. You answer questions about a tender specification (PTS)
    using the structured extraction data and graph facts provided below.

    Rules:
    - Always cite the source page for any claim. If a fact came from a graph
      edge (a reference or cross-section mention), cite the source section's
      page.
    - Be concise. Prefer bullet points for lists.
    - If the question concerns risk or toxic clauses, surface the exact
      clause text and its severity (High / Medium / Low).
    - If the data does not support an answer, say so explicitly — do not
      fabricate.
    - Answer in Korean unless the question is clearly in English.
    - In the JSON you return, populate `citations` with one entry per fact
      that supports your answer (category is one of: items, materials,
      standards, environmental, electrical, tests, toxic_clauses,
      references, sections). The answer MUST be grounded in those citations.
    """
).strip()


def _schema() -> dict[str, Any]:
    """OpenAI-compatible strict JSON schema for ChatAnswer."""
    schema = ChatAnswer.model_json_schema()
    _strict(schema)
    return schema


def _strict(node: dict) -> None:
    if not isinstance(node, dict):
        return
    node.pop("default", None)
    if node.get("type") == "object" and "properties" in node:
        node["additionalProperties"] = False
        node["required"] = list(node["properties"].keys())
        for v in node["properties"].values():
            _strict(v)
    for key in ("items", "anyOf", "allOf", "oneOf"):
        if key in node:
            sub = node[key]
            if isinstance(sub, list):
                for s in sub:
                    _strict(s)
            else:
                _strict(sub)
    if "$defs" in node:
        for s in node["$defs"].values():
            _strict(s)


async def _graph_facts(neo4j: Neo4jClient, doc_id: str) -> dict:
    """Pre-built Cypher queries that surface graph-only facts."""
    sections_with_stds = await neo4j.run_read(
        """
        MATCH (s:Section {doc_id: $doc_id})-[:MENTIONS]->(std:Standard)
        RETURN s.number AS section, s.title AS title, s.page_start AS page,
               collect(std.code)[..10] AS standards
        ORDER BY s.number
        """,
        {"doc_id": doc_id},
    )

    refers_edges = await neo4j.run_read(
        """
        MATCH (src:Section {doc_id: $doc_id})-[r:REFERS_TO]->(tgt)
        RETURN src.number AS src_section, src.page_start AS src_page,
               r.kind AS kind,
               coalesce(tgt.code, tgt.number) AS target,
               r.context AS context
        LIMIT 30
        """,
        {"doc_id": doc_id},
    )

    risks = await neo4j.run_read(
        """
        MATCH (d:Document {id: $doc_id})-[:HAS_RISK]->(tc:ToxicClause)
        RETURN tc.severity AS severity, tc.text AS text,
               tc.reason AS reason, tc.page AS page
        ORDER BY CASE tc.severity
                   WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2
                 END
        """,
        {"doc_id": doc_id},
    )

    return {
        "sections_with_standards": sections_with_stds,
        "refers_edges": refers_edges,
        "risks": risks,
    }


def _build_context(extraction, graph_facts: dict) -> str:
    ex = extraction.extracted
    lines: list[str] = []
    lines.append(f"DOCUMENT: {extraction.filename} ({extraction.page_count} pages)")
    lines.append("")

    def _fmt_list(title: str, items: list, template) -> None:
        if not items:
            return
        lines.append(f"## {title}")
        for it in items:
            lines.append(f"  - {template(it)}")
        lines.append("")

    _fmt_list(
        "Items (Table 1.1)",
        ex.items,
        lambda it: f"{it.stock_code}: {it.description} (p.{it.page})",
    )
    _fmt_list(
        "Materials",
        ex.materials,
        lambda m: f"{m.grade} [{m.standard}] (p.{m.page})",
    )
    _fmt_list(
        "Standards (declared)",
        ex.standards,
        lambda s: f"{s.code} — {s.title} (p.{s.page})",
    )
    _fmt_list(
        "Environmental",
        ex.environmental,
        lambda e: f"{e.type}: {e.value} {e.unit} (p.{e.page})",
    )
    _fmt_list(
        "Electrical",
        ex.electrical,
        lambda e: f"{e.type}: {e.value} {e.unit} (p.{e.page})",
    )
    _fmt_list(
        "Tests",
        ex.tests,
        lambda t: f"[{t.category}] {t.criterion} — {t.reference} (p.{t.page})",
    )
    _fmt_list(
        "Toxic clauses (rule-detected)",
        ex.toxic_clauses,
        lambda tc: f"[{tc.severity}] p.{tc.page}: {tc.text[:140]}  //{tc.reason}",
    )

    lines.append("## Graph facts (Neo4j)")
    lines.append(
        f"  sections with standards: {len(graph_facts['sections_with_standards'])}"
    )
    for row in graph_facts["sections_with_standards"][:6]:
        lines.append(
            f"    - §{row['section']} '{row['title']}' (p.{row['page']}) "
            f"→ {', '.join(row['standards'])}"
        )
    lines.append(f"  cross-references: {len(graph_facts['refers_edges'])}")
    for row in graph_facts["refers_edges"][:10]:
        lines.append(
            f"    - §{row['src_section']} (p.{row['src_page']}) "
            f"--{row['kind']}--> {row['target']}  ctx: \"{(row['context'] or '')[:100]}\""
        )
    lines.append(f"  toxic clauses in graph: {len(graph_facts['risks'])}")
    for row in graph_facts["risks"]:
        lines.append(
            f"    - [{row['severity']}] p.{row['page']}: "
            f"{(row['text'] or '')[:140]}  ({row['reason']})"
        )
    lines.append("")

    return "\n".join(lines)


async def answer_question(
    question: str,
    doc_id: str,
    llm: LLMClient,
    neo4j: Neo4jClient,
) -> ChatAnswer:
    extraction = await load_extraction(doc_id)
    if extraction is None:
        raise KeyError(doc_id)

    facts = await _graph_facts(neo4j, doc_id)
    context = _build_context(extraction, facts)

    messages: list[Message] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Question: {question}\n\n---\n{context}",
        },
    ]

    raw = await llm.complete_json(
        messages,
        schema=_schema(),
        temperature=0.2,
        max_tokens=1500,
    )
    answer = ChatAnswer.model_validate(raw)
    answer.used_graph_facts = (
        len(facts["sections_with_standards"])
        + len(facts["refers_edges"])
        + len(facts["risks"])
    )
    return answer
