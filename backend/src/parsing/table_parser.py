"""Table extraction. pdfplumber first (no system deps), Camelot as fallback."""

from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass
class ExtractedTable:
    page_number: int
    index_on_page: int
    headers: list[str]
    rows: list[list[str]]

    def to_dict(self) -> dict:
        return {
            "page": self.page_number,
            "index": self.index_on_page,
            "headers": self.headers,
            "rows": self.rows,
        }


def _clean_cell(cell: object) -> str:
    if cell is None:
        return ""
    return " ".join(str(cell).split())


def extract_tables(path: str | Path) -> list[ExtractedTable]:
    path = Path(path)
    out: list[ExtractedTable] = []

    with pdfplumber.open(path) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for t_idx, t in enumerate(tables):
                if not t or len(t) < 2:
                    continue
                headers = [_clean_cell(c) for c in t[0]]
                rows = [[_clean_cell(c) for c in row] for row in t[1:]]
                # drop fully empty rows
                rows = [r for r in rows if any(cell for cell in r)]
                if not rows:
                    continue
                out.append(
                    ExtractedTable(
                        page_number=page_idx,
                        index_on_page=t_idx,
                        headers=headers,
                        rows=rows,
                    )
                )
    return out
