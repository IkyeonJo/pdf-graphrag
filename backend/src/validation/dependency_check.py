"""Cross-validation: company standard (Korean JSON) ↔ extracted document.

Implements the R001~R005 rules declared in
/data/standards/company_std.ko.json. Each rule produces a ValidationIssue
with severity, evidence pages, and a Korean-language explanation — ready
to render in the Human-in-the-loop review UI.

The rules themselves are the core Graph RAG selling point: "우리 기준 DB ↔
상대 사양서"를 교차로 질의해 독소를 가려낸다.
"""

import json
import re
from pathlib import Path

from pydantic import BaseModel

from src.core.storage import load as load_extraction

_STANDARD_PATH = Path("/data/standards/company_std.ko.json")


class Evidence(BaseModel):
    description: str
    page: int | None = None


class ValidationIssue(BaseModel):
    rule_id: str
    severity: str                 # "High" | "Medium" | "Low"
    title: str
    detail: str
    evidence: list[Evidence]


class ValidationReport(BaseModel):
    doc_id: str
    issues: list[ValidationIssue]
    passed: list[str]             # rule_ids that passed


def _load_standard() -> dict:
    if not _STANDARD_PATH.exists():
        return {}
    return json.loads(_STANDARD_PATH.read_text(encoding="utf-8"))


def _parse_temp(text: str) -> list[int]:
    """Extract integer °C values from a free-form string (e.g. 'Peak: 40°C, Min: 10°C')."""
    return [int(m.group(1)) for m in re.finditer(r"(-?\d{1,3})\s?[°º]?\s?C", text)]


def _range_covers(outer: tuple[int, int], inner: tuple[int, int], margin: int = 5) -> bool:
    low_o, high_o = outer
    low_i, high_i = inner
    return (low_o <= low_i - margin) and (high_o >= high_i + margin)


async def run_validation(doc_id: str) -> ValidationReport:
    extraction = await load_extraction(doc_id)
    if extraction is None:
        raise KeyError(f"doc {doc_id} not found")

    std = _load_standard()
    ex = extraction.extracted
    issues: list[ValidationIssue] = []
    passed: list[str] = []

    # ── R001: 염분 환경 + SUS304 사용 → High
    atmosphere_entries = [e for e in ex.environmental if "atmosphere" in e.type.lower()]
    saliferous = any(
        "saliferous" in e.value.lower() or "corros" in e.value.lower()
        for e in atmosphere_entries
    )
    forbidden = set(std.get("재질", {}).get("금지_재질", []))
    forbidden_upper = {m.upper() for m in forbidden}
    used_forbidden = [m for m in ex.materials if m.grade.upper() in forbidden_upper]

    if saliferous and used_forbidden:
        evidence: list[Evidence] = []
        for e in atmosphere_entries:
            evidence.append(
                Evidence(
                    description=f"대기 조건: {e.value}",
                    page=e.page,
                )
            )
        for m in used_forbidden:
            evidence.append(
                Evidence(
                    description=f"금지 재질 사용: {m.grade}",
                    page=m.page,
                )
            )
        issues.append(
            ValidationIssue(
                rule_id="R001",
                severity="High",
                title="염분 환경에 금지 재질 사용",
                detail=(
                    f"대기조건에 saliferous/corrosive가 명시되어 있으나 "
                    f"{', '.join(m.grade for m in used_forbidden)} 재질이 사용됨. "
                    f"당사 표준상 이 환경에선 {', '.join(std['재질']['허용_스테인리스_등급'])}만 허용됩니다. "
                    f"사유: {std['재질']['금지_사유']}"
                ),
                evidence=evidence,
            )
        )
    else:
        passed.append("R001")

    # ── R002: 보관 온도 범위가 사용 주변온도 범위를 포함하는지 (마진 5℃)
    ambient_entries = [e for e in ex.environmental if "temperature" in e.type.lower()]
    storage_entries = [s for s in ex.storage if s.description]

    ambient_temps: list[int] = []
    for e in ambient_entries:
        ambient_temps.extend(_parse_temp(e.value))
    storage_temps: list[int] = []
    for s in storage_entries:
        storage_temps.extend(_parse_temp(s.description))

    if ambient_temps and storage_temps:
        ambient_range = (min(ambient_temps), max(ambient_temps))
        storage_range = (min(storage_temps), max(storage_temps))
        if not _range_covers(storage_range, ambient_range, margin=5):
            issues.append(
                ValidationIssue(
                    rule_id="R002",
                    severity="Medium",
                    title="보관 온도 범위가 사용 환경을 포함하지 못함",
                    detail=(
                        f"보관 범위 {storage_range[0]}~{storage_range[1]}℃가 "
                        f"사용 주변온도 범위 {ambient_range[0]}~{ambient_range[1]}℃를 "
                        f"마진 5℃로 포함하지 않습니다. 동일한 한계에서 보관/운용 시 "
                        f"구조 피로가 축적됩니다."
                    ),
                    evidence=[
                        Evidence(description=f"사용 온도: {e.value}", page=e.page)
                        for e in ambient_entries
                    ]
                    + [
                        Evidence(description=f"보관 조건: {s.description}", page=s.page)
                        for s in storage_entries
                    ],
                )
            )
        else:
            passed.append("R002")
    else:
        passed.append("R002")

    # ── R003: 본문에서 참조된 표준이 Standards 목록에 있는지
    referenced_codes: set[str] = set()
    for ref in extraction.references:
        if ref.kind == "standard":
            referenced_codes.add(ref.target.upper())
    declared_codes = {s.code.upper() for s in ex.standards}
    missing = sorted(
        code
        for code in referenced_codes
        # strip ".x" sub-clauses so "AS 1154.1" counts as declared if "AS 1154" is listed
        if code not in declared_codes
        and code.rsplit(".", 1)[0] not in declared_codes
    )
    if missing:
        issues.append(
            ValidationIssue(
                rule_id="R003",
                severity="Low",
                title="References 섹션에서 누락된 참조 표준",
                detail=(
                    f"본문에서 {len(missing)}개 표준이 참조되나 References/Applicable "
                    f"Standards 섹션에 명시되지 않았습니다: {', '.join(missing)}"
                ),
                evidence=[
                    Evidence(description=f"누락 표준: {code}") for code in missing
                ],
            )
        )
    else:
        passed.append("R003")

    # ── R004: 체결요소(Bolts, Nuts, Washers) 카테고리가 강도등급/나사공차 포함 요건
    bolt_items = [
        it for it in ex.items if re.search(r"bolt|nut|washer", it.description, re.I)
    ]
    required_grades = set(std.get("체결요소_표준", {}).get("허용_강도등급", []))
    required_tolerances = set(std.get("체결요소_표준", {}).get("나사_공차", []))

    mentions_grade = any(
        any(g in f"{it.description}" for g in required_grades) for it in bolt_items
    )
    mentions_tolerance = any(
        any(t in f"{it.description}" for t in required_tolerances) for it in bolt_items
    )
    # Fall back to scanning extracted dimensions/marking text for these tokens
    all_text = " ".join(
        [it.description for it in ex.items]
        + [d.subject + " " + d.value for d in ex.dimensions]
        + [m.description for m in ex.marking]
    )
    tolerance_in_text = any(t in all_text for t in required_tolerances)
    grade_in_text = any(g in all_text for g in required_grades)

    missing_attrs = []
    if not (mentions_grade or grade_in_text):
        missing_attrs.append("강도등급")
    if not (mentions_tolerance or tolerance_in_text):
        missing_attrs.append("나사공차")
    if bolt_items and missing_attrs:
        issues.append(
            ValidationIssue(
                rule_id="R004",
                severity="Medium",
                title="체결요소에 강도등급/나사공차 명시 누락",
                detail=(
                    f"{len(bolt_items)}개 체결요소 품목이 있으나 {', '.join(missing_attrs)} "
                    f"정보가 문서 어디에도 명시되지 않았습니다. 당사 표준은 "
                    f"강도등급 {sorted(required_grades)}, 나사공차 {sorted(required_tolerances)} 필수."
                ),
                evidence=[
                    Evidence(description=it.description, page=it.page)
                    for it in bolt_items[:3]
                ],
            )
        )
    else:
        passed.append("R004")

    # ── R005: 서비스 수명 > 40년 → High (독소조항 flagger가 이미 잡지만, 여기서는 rule로 재확인)
    max_life = int(std.get("독소조항_기준", {}).get("과도한_수명_요구_년", 40))
    years_found: list[tuple[int, int | None]] = []
    for entry in ex.lifespan:
        for m in re.finditer(r"(\d{2,3})\s*year", entry.description, re.I):
            years = int(m.group(1))
            if years > max_life:
                years_found.append((years, entry.page))
    for tc in ex.toxic_clauses:
        for m in re.finditer(r"(\d{2,3})\s*year", tc.text, re.I):
            years = int(m.group(1))
            if years > max_life:
                years_found.append((years, tc.page))

    if years_found:
        max_year = max(y for y, _ in years_found)
        issues.append(
            ValidationIssue(
                rule_id="R005",
                severity="High",
                title="과도한 서비스 수명 요구",
                detail=(
                    f"서비스 수명 {max_year}년이 당사 기준 {max_life}년을 초과합니다. "
                    f"제조물 책임 기간 및 예비 부품 조달 비용이 비대칭적으로 증가합니다."
                ),
                evidence=[
                    Evidence(description=f"요구 수명: {y}년", page=p)
                    for y, p in years_found
                ],
            )
        )
    else:
        passed.append("R005")

    return ValidationReport(doc_id=doc_id, issues=issues, passed=passed)
