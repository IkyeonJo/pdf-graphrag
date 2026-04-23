"""Rule-based toxic clause detection.

Loads the company standard JSON (한글 사내 기준) and scans the PDF for
unfavorable clauses. LLM-based detection in Tier 2 tends to miss these,
so we combine both: rules guarantee coverage, LLM adds nuance.
"""

import json
import re
from pathlib import Path

from src.extraction.schemas import ToxicClause
from src.parsing.pdf_loader import PageContent

_STANDARD_PATH = Path("/data/standards/company_std.ko.json")


def _load_standard() -> dict:
    if not _STANDARD_PATH.exists():
        return {}
    return json.loads(_STANDARD_PATH.read_text(encoding="utf-8"))


def _sentence_around(text: str, start: int, end: int, radius: int = 180) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right]

    # trim to nearest sentence boundary on the left
    for marker in (". ", ".\n", "•", "\n\n"):
        idx = snippet.find(marker, 0, start - left)
        if idx >= 0:
            snippet = snippet[idx + len(marker) :]
            break

    # trim on the right
    for marker in (". ", ".\n", "\n\n"):
        idx = snippet.find(marker, end - left)
        if idx >= 0:
            snippet = snippet[: idx + 1]
            break

    return " ".join(snippet.split())


def detect_toxic_clauses(pages: list[PageContent]) -> list[ToxicClause]:
    std = _load_standard()
    config = std.get("독소조항_기준", {})

    high_kw: list[str] = config.get("즉시_거절_키워드", [])
    med_kw: list[str] = config.get("협상_필요_키워드", [])
    sla = config.get("SLA_임계값", {})
    sla_days_min = int(sla.get("샘플제공_최소일수", 7))
    sla_hours_min = int(sla.get("서류응답_최소시간", 24))
    sla_lead_weeks_min = int(sla.get("납기_최소주수", 0))
    max_life_years = int(config.get("과도한_수명_요구_년", 40))

    out: list[ToxicClause] = []
    seen: set[tuple[str, int]] = set()

    def _add(clause: ToxicClause) -> None:
        key = (clause.text[:120], clause.page or 0)
        if key in seen:
            return
        seen.add(key)
        out.append(clause)

    for p in pages:
        text = p.text

        for kw in high_kw:
            for m in re.finditer(re.escape(kw), text, re.IGNORECASE):
                _add(
                    ToxicClause(
                        text=_sentence_around(text, m.start(), m.end()),
                        severity="High",
                        reason=f"즉시 거절 키워드 '{kw}' 포함",
                        page=p.page_number,
                    )
                )

        for kw in med_kw:
            for m in re.finditer(re.escape(kw), text, re.IGNORECASE):
                _add(
                    ToxicClause(
                        text=_sentence_around(text, m.start(), m.end()),
                        severity="Medium",
                        reason=f"협상 필요 키워드 '{kw}' 포함",
                        page=p.page_number,
                    )
                )

        # SLA: "within X hours", "within X business hours"
        for m in re.finditer(
            r"within\s+(\d+)\s+(?:business\s+)?hours?", text, re.IGNORECASE
        ):
            hours = int(m.group(1))
            if hours <= sla_hours_min:
                _add(
                    ToxicClause(
                        text=_sentence_around(text, m.start(), m.end()),
                        severity="Medium",
                        reason=f"SLA 응답 임계값 초과 부담: {hours}시간 ≤ 기준 {sla_hours_min}시간",
                        page=p.page_number,
                    )
                )

        # SLA: "within X days"
        for m in re.finditer(r"within\s+(\d+)\s+days?", text, re.IGNORECASE):
            days = int(m.group(1))
            if days <= sla_days_min:
                _add(
                    ToxicClause(
                        text=_sentence_around(text, m.start(), m.end()),
                        severity="Medium",
                        reason=f"SLA 샘플/응답 임계값 초과 부담: {days}일 ≤ 기준 {sla_days_min}일",
                        page=p.page_number,
                    )
                )

        # Short lead time: "within X weeks"
        if sla_lead_weeks_min:
            for m in re.finditer(r"within\s+(\d+)\s+weeks?", text, re.IGNORECASE):
                weeks = int(m.group(1))
                if weeks < sla_lead_weeks_min:
                    _add(
                        ToxicClause(
                            text=_sentence_around(text, m.start(), m.end()),
                            severity="Medium",
                            reason=f"납기 임계값 미달: {weeks}주 < 기준 {sla_lead_weeks_min}주",
                            page=p.page_number,
                        )
                    )

        # Excessive service life: "service life of X years"
        for m in re.finditer(
            r"service\s+life\s+of\s+(\d+)\s+years?", text, re.IGNORECASE
        ):
            years = int(m.group(1))
            if years > max_life_years:
                _add(
                    ToxicClause(
                        text=_sentence_around(text, m.start(), m.end()),
                        severity="High",
                        reason=f"과도한 수명 요구: {years}년 > 기준 {max_life_years}년",
                        page=p.page_number,
                    )
                )

    return out
