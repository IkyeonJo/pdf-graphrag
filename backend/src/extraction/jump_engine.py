"""Cross-reference detection and resolution (the "Jump Engine").

Scans each page for reference expressions and resolves them to concrete
targets (page numbers for internal refs, Standard nodes for external refs).

Examples from MR-161:
    "dimensions mentioned in Table 1.1"   → internal  → Table 1.1 @ page 5
    "in accordance with AS 1111"          → external → Standard AS 1111
    "Clause 2.2 of AS 1154.1"             → external → Standard AS 1154.1
    "see Appendix A"                      → internal → Appendix A @ page 1
"""

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from src.parsing import PageContent, SectionIndex


RefKind = Literal["table", "section", "clause", "appendix", "standard"]


@dataclass
class _Pattern:
    regex: re.Pattern[str]
    kind: RefKind


_PATTERNS: list[_Pattern] = [
    _Pattern(re.compile(r"\bTable\s+(\d+\.\d+)\b", re.IGNORECASE), "table"),
    _Pattern(
        re.compile(r"\b(?:Section|Sections)\s+(\d+(?:\.\d+)+)\b", re.IGNORECASE),
        "section",
    ),
    _Pattern(
        re.compile(r"\bClause\s+(\d+(?:\.\d+)+)\b", re.IGNORECASE),
        "clause",
    ),
    _Pattern(
        re.compile(r"\b(?:Appendix|Annex)\s+([A-Z])\b", re.IGNORECASE),
        "appendix",
    ),
    _Pattern(
        re.compile(
            r"\b(AS(?:/NZS)?|ISO|IEC|KS)\s?(\d{3,5}(?:\.\d+)?)\b",
            re.IGNORECASE,
        ),
        "standard",
    ),
]


class Reference(BaseModel):
    kind: RefKind
    target: str               # "1.1", "A", "AS 1154.1"
    source_page: int
    source_section: str | None = None
    target_page: int | None = None   # resolved, if internal
    context: str              # ~120-char surrounding snippet


def _context(text: str, start: int, end: int, radius: int = 80) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


def _section_for(page: int, sections: list, best_section_fn) -> str | None:
    return best_section_fn(sections, page)


def detect_references(
    pages: list[PageContent],
    section_index: SectionIndex,
    best_section_fn,
) -> list[Reference]:
    out: list[Reference] = []
    seen: set[tuple[str, str, int]] = set()

    for p in pages:
        for pat in _PATTERNS:
            for m in pat.regex.finditer(p.text):
                if pat.kind == "standard":
                    prefix = m.group(1).upper().replace(" ", "")
                    num = m.group(2)
                    target = f"{prefix} {num}"
                    target = re.sub(r"\s+", " ", target).strip()
                else:
                    target = m.group(1)

                key = (pat.kind, target, p.page_number)
                if key in seen:
                    continue
                seen.add(key)

                target_page: int | None = None
                if pat.kind == "table":
                    # Tables are labelled as "Table X.Y" inside page text. Pages
                    # where such a label occurs are treated as the target.
                    target_page = _find_table_page(pages, target)
                elif pat.kind in ("section", "clause"):
                    sec = section_index.by_number(target)
                    target_page = sec.page_start if sec else None
                elif pat.kind == "appendix":
                    target_page = section_index.appendices.get(target.upper())
                # standard: external, no target_page

                out.append(
                    Reference(
                        kind=pat.kind,
                        target=target,
                        source_page=p.page_number,
                        source_section=best_section_fn(
                            [s for s in section_index.sections], p.page_number
                        ),
                        target_page=target_page,
                        context=_context(p.text, m.start(), m.end()),
                    )
                )
    return out


def _find_table_page(pages: list[PageContent], table_number: str) -> int | None:
    """Locate the page on which the table is *defined* (not just referenced).

    We look for a caption like 'Table 1.1:' or 'Table 1.1 Items ...'.
    """
    pattern = re.compile(
        rf"Table\s+{re.escape(table_number)}\s*[:\.\-—]",
        re.IGNORECASE,
    )
    for p in pages:
        if pattern.search(p.text):
            return p.page_number
    return None
