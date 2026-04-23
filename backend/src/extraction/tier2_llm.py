"""LLM-based extraction into the 15-category schema.

Single-shot extraction for MVP: the whole document text is passed with a
strict JSON schema. For larger documents (3000 pages in PRD), Phase 2 will
split by section and merge.
"""

import textwrap

from src.extraction.schemas import ExtractedDocument, llm_json_schema
from src.llm.base import LLMClient, Message
from src.parsing.pdf_loader import PageContent

SYSTEM_PROMPT = textwrap.dedent(
    """\
    You are an expert engineering-document analyst for a Korean steel manufacturer (코리아스틸).
    Extract structured facts from tender specifications (PTS) into the provided JSON schema.

    Rules:
    - Populate every top-level key; use empty arrays if nothing applies.
    - For each entity, include the `page` number where it is mentioned (1-indexed).
    - Do NOT fabricate values. If a field is absent in the text, omit that entity.
    - Standards (AS/ISO/IEC/KS) go in `standards`, not scattered across other categories.
    - Values stay in their original language (English text in the input stays English).
    - For `toxic_clauses`, copy the exact clause text and grade severity:
        * "High" — automatic rejection, unlimited liability, excessive lifetime (>40y)
        * "Medium" — cost transfer to supplier, unreasonable SLA (<24h / <7d)
        * "Low" — minor inconvenience
    """
).strip()


def _build_user_prompt(pages: list[PageContent], tables_summary: str) -> str:
    body_parts = [f"--- Page {p.page_number} ---\n{p.text}" for p in pages]
    body = "\n\n".join(body_parts)
    return textwrap.dedent(
        f"""\
        Document text (page-delimited):

        {body}

        Parsed tables (structured):

        {tables_summary}

        Return a single JSON object matching the schema.
        """
    )


async def extract_structured(
    client: LLMClient,
    pages: list[PageContent],
    tables_summary: str,
) -> ExtractedDocument:
    messages: list[Message] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(pages, tables_summary)},
    ]
    raw = await client.complete_json(
        messages,
        schema=llm_json_schema(),
        temperature=0.0,
        max_tokens=8000,
    )
    return ExtractedDocument.model_validate(raw)
