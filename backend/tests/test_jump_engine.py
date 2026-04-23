"""Unit tests for the Jump Engine.

Cases are pinned to the real MR-161 sample so the suite doubles as a
regression check for the Graph RAG demo's headline feature.
"""

from src.extraction.jump_engine import detect_references
from src.parsing.pdf_loader import PageContent
from src.parsing.toc_extractor import Section, SectionIndex


def _fake_sections() -> SectionIndex:
    idx = SectionIndex()
    idx.sections = [
        Section(number="1.0", title="Introduction", page_start=5, page_end=5, depth=1),
        Section(number="2.1", title="Applicable Standards", page_start=6, page_end=6, depth=2),
        Section(number="4.2", title="Workmanship", page_start=7, page_end=8, depth=2),
        Section(number="14.1", title="Technical Details", page_start=12, page_end=13, depth=2),
    ]
    idx.appendices = {"A": 1}
    return idx


def _best_section_stub(_sections, page: int | None) -> str | None:
    if page is None:
        return None
    # pick any covering section — tests don't depend on specificity
    return "4.2" if page in (7, 8) else "2.1" if page == 6 else "1.0"


def test_detects_table_and_resolves_to_defining_page() -> None:
    pages = [
        PageContent(
            page_number=5,
            text="Table 1.1: Items Covered Under this Specification\nNo. Stock Code Item\n",
            char_count=100,
        ),
        PageContent(
            page_number=7,
            text="Forgings shall be finished to the dimensions mentioned in Table 1.1 or AS 1154.1.",
            char_count=80,
        ),
    ]
    idx = _fake_sections()
    refs = detect_references(pages, idx, _best_section_stub)

    table_refs = [r for r in refs if r.kind == "table"]
    assert any(r.target == "1.1" and r.target_page == 5 for r in table_refs)


def test_detects_appendix_reference() -> None:
    pages = [
        PageContent(page_number=1, text="APPENDIX A\nTECHNICAL SPECIFICATION", char_count=40),
        PageContent(page_number=3, text="All tenderers shall complete Appendix A.", char_count=40),
    ]
    idx = _fake_sections()
    refs = detect_references(pages, idx, _best_section_stub)
    appx = [r for r in refs if r.kind == "appendix"]
    assert any(r.target.upper() == "A" and r.target_page == 1 for r in appx)


def test_detects_standard_reference_with_clause() -> None:
    pages = [
        PageContent(
            page_number=7,
            text=(
                "The steel shall be selected from Clause 1.4.6.2 of AS 1154.1 "
                "for grade 304 or 316."
            ),
            char_count=120,
        ),
    ]
    idx = _fake_sections()
    refs = detect_references(pages, idx, _best_section_stub)

    std_refs = [r for r in refs if r.kind == "standard"]
    assert any("AS 1154.1" in r.target for r in std_refs)

    clause_refs = [r for r in refs if r.kind == "clause"]
    assert any(r.target == "1.4.6.2" for r in clause_refs)


def test_deduplicates_same_reference_on_same_page() -> None:
    pages = [
        PageContent(
            page_number=7,
            text="AS 1111 defines threading. AS 1111 is required. AS 1111.",
            char_count=80,
        ),
    ]
    idx = _fake_sections()
    refs = detect_references(pages, idx, _best_section_stub)
    as1111 = [r for r in refs if r.kind == "standard" and r.target == "AS 1111"]
    assert len(as1111) == 1


def test_context_snippet_contains_surrounding_words() -> None:
    text = (
        "This specification cross references Table 1.1 in the items list. "
        "All tenderers must confirm."
    )
    pages = [PageContent(page_number=5, text=text, char_count=len(text))]
    idx = _fake_sections()
    refs = detect_references(pages, idx, _best_section_stub)
    assert refs
    assert "Table 1.1" in refs[0].context
