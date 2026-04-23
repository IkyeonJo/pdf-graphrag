from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class PageContent:
    page_number: int  # 1-indexed
    text: str
    char_count: int


def load_pdf(path: str | Path) -> list[PageContent]:
    """Return per-page text. 1-indexed page numbers to match PDF viewer convention."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    pages: list[PageContent] = []
    with fitz.open(path) as doc:
        for idx, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            pages.append(
                PageContent(
                    page_number=idx,
                    text=text,
                    char_count=len(text),
                )
            )
    return pages


def full_text(pages: list[PageContent]) -> str:
    return "\n\n".join(f"[Page {p.page_number}]\n{p.text}" for p in pages)
