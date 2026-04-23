"""Parse Table of Contents to map section numbers → pages.

TOC lines in MR-161 look like:
    "4.2   Workmanship ....................... 7"
    "14.1 Technical Details – Stainless Steel Fittings ... 12"

Result is used by the Jump Engine to resolve cross-references like
"see Section 4.2" or "Appendix A" to concrete page ranges.
"""

import re
from dataclasses import dataclass, field

from src.parsing.pdf_loader import PageContent

TOC_ENTRY_RE = re.compile(
    r"""
    ^\s*
    (?P<number>\d+(?:\.\d+)*)\s+       # "4", "4.2", "14.1"
    (?P<title>.+?)                      # section title (non-greedy)
    \s*\.{2,}\s*                        # dotted leader
    (?P<page>\d+)\s*$                   # trailing page number
    """,
    re.VERBOSE | re.MULTILINE,
)

APPENDIX_HEADER_RE = re.compile(r"^\s*APPENDIX\s+([A-Z])\b", re.IGNORECASE | re.MULTILINE)


def _effective_depth(number: str) -> int:
    """Hierarchical depth, stripping trailing '.0' so '2.0' is a parent of '2.1'.

    '1.0' → 1, '2.1' → 2, '3.2.1' → 3, '4.0.0' → 1.
    """
    parts = number.split(".")
    while len(parts) > 1 and parts[-1] == "0":
        parts.pop()
    return len(parts)


@dataclass
class Section:
    number: str              # "4.2"
    title: str               # "Workmanship"
    page_start: int
    page_end: int | None = None
    depth: int = 1           # 1 for "4", 2 for "4.2", ...


@dataclass
class SectionIndex:
    sections: list[Section] = field(default_factory=list)
    appendices: dict[str, int] = field(default_factory=dict)  # "A" -> page

    def resolve(self, ref: str) -> Section | None:
        """Resolve a textual reference like '4.2' or 'Section 6.1'."""
        m = re.search(r"\d+(?:\.\d+)*", ref)
        if not m:
            return None
        number = m.group(0)
        for s in self.sections:
            if s.number == number:
                return s
        return None

    def by_number(self, number: str) -> Section | None:
        for s in self.sections:
            if s.number == number:
                return s
        return None


def build_section_index(pages: list[PageContent]) -> SectionIndex:
    index = SectionIndex()
    if not pages:
        return index

    # TOC usually sits in the first ~5 pages. Scan aggressively.
    scan_text = "\n".join(p.text for p in pages[: min(5, len(pages))])

    seen: set[str] = set()
    for m in TOC_ENTRY_RE.finditer(scan_text):
        number = m.group("number")
        if number in seen:
            continue
        seen.add(number)
        title = m.group("title").strip().rstrip(".")
        page = int(m.group("page"))
        index.sections.append(
            Section(
                number=number,
                title=title,
                page_start=page,
                depth=_effective_depth(number),
            )
        )

    # sort by (page, number) and fill in page_end from next section's start
    index.sections.sort(key=lambda s: (s.page_start, s.number))
    for i, s in enumerate(index.sections):
        next_start = (
            index.sections[i + 1].page_start if i + 1 < len(index.sections) else None
        )
        if next_start is not None and next_start >= s.page_start:
            s.page_end = next_start
        else:
            s.page_end = pages[-1].page_number

    # appendices: scan all pages for "APPENDIX X"
    for p in pages:
        for m in APPENDIX_HEADER_RE.finditer(p.text):
            letter = m.group(1).upper()
            index.appendices.setdefault(letter, p.page_number)

    return index
