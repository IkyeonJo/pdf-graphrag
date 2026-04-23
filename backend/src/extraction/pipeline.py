"""End-to-end extraction pipeline.

1. Load PDF → pages
2. Build TOC / section index
3. Parse tables
4. Tier 1 rule hits (standards, voltages, temps, materials...)
5. Tier 2 LLM extraction (15 categories)
6. Merge rule hits into LLM output (adds deterministic coverage)

Returns a Pydantic ExtractionResult ready to serialize to JSON and feed into Neo4j.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from src.extraction.jump_engine import Reference, detect_references
from src.extraction.schemas import (
    ElectricalSpec,
    EnvCondition,
    ExtractedDocument,
    Material,
    StandardRef,
    ToxicClause,
)
from src.extraction.tier1_rules import RuleHit, scan_pages
from src.extraction.tier2_llm import extract_structured
from src.extraction.toxic_rules import detect_toxic_clauses
from src.llm.base import LLMClient
from src.parsing import (
    ExtractedTable,
    PageContent,
    SectionIndex,
    build_section_index,
    extract_tables,
    load_pdf,
)


class SectionOut(BaseModel):
    number: str
    title: str
    page_start: int
    page_end: int | None
    depth: int


class ExtractionResult(BaseModel):
    doc_id: str
    filename: str
    page_count: int
    sections: list[SectionOut]
    appendices: dict[str, int]
    tables: list[dict]
    rule_hits: list[dict]
    references: list[Reference]
    extracted: ExtractedDocument


@dataclass
class _PipelineContext:
    pages: list[PageContent] = field(default_factory=list)
    sections: SectionIndex = field(default_factory=SectionIndex)
    tables: list[ExtractedTable] = field(default_factory=list)
    rule_hits: list[RuleHit] = field(default_factory=list)


def _summarize_tables(tables: list[ExtractedTable], limit: int = 6) -> str:
    if not tables:
        return "(no tables parsed)"
    out: list[str] = []
    for t in tables[:limit]:
        out.append(
            json.dumps(
                {
                    "page": t.page_number,
                    "headers": t.headers,
                    "rows": t.rows[:30],
                },
                ensure_ascii=False,
            )
        )
    if len(tables) > limit:
        out.append(f"... (+{len(tables) - limit} more tables)")
    return "\n".join(out)


def _merge_toxic_clauses(
    extracted: ExtractedDocument, detected: list[ToxicClause]
) -> ExtractedDocument:
    """Merge rule-detected toxic clauses with LLM ones, de-duping on text prefix."""
    existing = {tc.text[:120].lower(): tc for tc in extracted.toxic_clauses}
    for tc in detected:
        key = tc.text[:120].lower()
        if key not in existing:
            extracted.toxic_clauses.append(tc)
            existing[key] = tc
    return extracted


def _merge_rule_hits(extracted: ExtractedDocument, hits: list[RuleHit]) -> ExtractedDocument:
    """Add rule-based hits not already covered by LLM extraction."""
    standard_codes = {s.code.upper() for s in extracted.standards}
    material_grades = {m.grade.upper() for m in extracted.materials}
    electrical_types_values = {(e.type.lower(), e.value.lower()) for e in extracted.electrical}
    env_types_values = {(e.type.lower(), e.value.lower()) for e in extracted.environmental}

    for h in hits:
        if h.kind == "standard" and h.value.upper() not in standard_codes:
            extracted.standards.append(StandardRef(code=h.value, page=h.page))
            standard_codes.add(h.value.upper())
        elif h.kind == "material_grade" and h.value.upper() not in material_grades:
            extracted.materials.append(Material(grade=h.value, page=h.page))
            material_grades.add(h.value.upper())
        elif h.kind == "voltage":
            key = ("nominal voltage", h.value.lower())
            if key not in electrical_types_values:
                extracted.electrical.append(
                    ElectricalSpec(type="Nominal Voltage", value=h.value, page=h.page)
                )
                electrical_types_values.add(key)
        elif h.kind == "frequency":
            key = ("frequency", h.value.lower())
            if key not in electrical_types_values:
                extracted.electrical.append(
                    ElectricalSpec(type="Frequency", value=h.value, page=h.page)
                )
                electrical_types_values.add(key)
        elif h.kind == "temperature":
            key = ("temperature", h.value.lower())
            if key not in env_types_values:
                extracted.environmental.append(
                    EnvCondition(type="Temperature", value=h.value, page=h.page)
                )
                env_types_values.add(key)
        elif h.kind == "humidity":
            key = ("humidity", h.value.lower())
            if key not in env_types_values:
                extracted.environmental.append(
                    EnvCondition(type="Humidity", value=h.value, page=h.page)
                )
                env_types_values.add(key)
    return extracted


async def run_pipeline(
    pdf_path: str | Path,
    doc_id: str,
    llm: LLMClient,
) -> ExtractionResult:
    pdf_path = Path(pdf_path)

    ctx = _PipelineContext()
    ctx.pages = load_pdf(pdf_path)
    ctx.sections = build_section_index(ctx.pages)
    ctx.tables = extract_tables(pdf_path)
    ctx.rule_hits = scan_pages(ctx.pages)

    tables_summary = _summarize_tables(ctx.tables)
    extracted = await extract_structured(llm, ctx.pages, tables_summary)
    extracted = _merge_rule_hits(extracted, ctx.rule_hits)
    extracted = _merge_toxic_clauses(extracted, detect_toxic_clauses(ctx.pages))

    sections_out = [
        SectionOut(
            number=s.number,
            title=s.title,
            page_start=s.page_start,
            page_end=s.page_end,
            depth=s.depth,
        )
        for s in ctx.sections.sections
    ]

    # Lazy import to avoid circular import with graph.builder.
    from src.graph.builder import _find_best_section

    references = detect_references(
        ctx.pages,
        ctx.sections,
        best_section_fn=lambda _sections, page: _find_best_section(sections_out, page),
    )

    return ExtractionResult(
        doc_id=doc_id,
        filename=pdf_path.name,
        page_count=len(ctx.pages),
        sections=sections_out,
        appendices=ctx.sections.appendices,
        tables=[t.to_dict() for t in ctx.tables],
        rule_hits=[{"kind": h.kind, "value": h.value, "page": h.page} for h in ctx.rule_hits],
        references=references,
        extracted=extracted,
    )
