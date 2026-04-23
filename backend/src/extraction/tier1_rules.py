"""Deterministic rule-based extraction.

High precision patterns for tokens LLMs often mangle: standard codes,
voltages, temperatures, humidities. Results are merged with Tier 2 output.
"""

import re
from dataclasses import dataclass

from src.parsing.pdf_loader import PageContent

STANDARD_RE = re.compile(
    r"\b(?:AS(?:/NZS)?|ISO|IEC|KS)\s?"
    r"(?:ISO\s?)?"
    r"\d{3,5}(?:\.\d+)?(?:[-:]?\d+)?\b"
)
VOLTAGE_RE = re.compile(r"\b\d{2,4}\s?(?:V|kV)\b", re.IGNORECASE)
FREQUENCY_RE = re.compile(r"\b\d{2,3}\s?Hz\b", re.IGNORECASE)
TEMPERATURE_RE = re.compile(r"-?\d{1,3}\s?[°º]?\s?C\b")
HUMIDITY_RE = re.compile(r"\b\d{1,3}\s?%\b")
RAINFALL_RE = re.compile(r"\b\d{2,5}\s?mm\b", re.IGNORECASE)
STAINLESS_GRADE_RE = re.compile(r"\b(?:grade\s+)?(?:SUS)?3(?:04|16)L?\b", re.IGNORECASE)
BOLT_SIZE_RE = re.compile(r"\bM\d{2,3}\s?x\s?M?\d{1,3}\b", re.IGNORECASE)


@dataclass
class RuleHit:
    kind: str
    value: str
    page: int


def scan_pages(pages: list[PageContent]) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for p in pages:
        hits.extend(_scan(p.text, p.page_number))
    # de-duplicate by (kind, value, page)
    seen: set[tuple[str, str, int]] = set()
    unique: list[RuleHit] = []
    for h in hits:
        key = (h.kind, h.value.lower(), h.page)
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
    return unique


def _scan(text: str, page: int) -> list[RuleHit]:
    out: list[RuleHit] = []
    for m in STANDARD_RE.finditer(text):
        out.append(RuleHit("standard", _normalize_standard(m.group(0)), page))
    for m in VOLTAGE_RE.finditer(text):
        out.append(RuleHit("voltage", _normalize(m.group(0)), page))
    for m in FREQUENCY_RE.finditer(text):
        out.append(RuleHit("frequency", _normalize(m.group(0)), page))
    for m in TEMPERATURE_RE.finditer(text):
        out.append(RuleHit("temperature", _normalize_temp(m.group(0)), page))
    for m in HUMIDITY_RE.finditer(text):
        out.append(RuleHit("humidity", _normalize(m.group(0)), page))
    for m in RAINFALL_RE.finditer(text):
        out.append(RuleHit("rainfall", _normalize(m.group(0)), page))
    for m in STAINLESS_GRADE_RE.finditer(text):
        out.append(RuleHit("material_grade", _normalize_material(m.group(0)), page))
    for m in BOLT_SIZE_RE.finditer(text):
        out.append(RuleHit("bolt_size", _normalize(m.group(0)), page))
    return out


def _normalize(s: str) -> str:
    return " ".join(s.split()).strip()


def _normalize_standard(s: str) -> str:
    s = _normalize(s).upper()
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_temp(s: str) -> str:
    s = _normalize(s)
    s = s.replace("º", "°")
    if "°" not in s:
        s = s.replace("C", "°C")
    return s


def _normalize_material(s: str) -> str:
    s = _normalize(s).upper().replace("GRADE ", "")
    if not s.startswith("SUS"):
        s = "SUS" + re.sub(r"\D", "", s) + ("L" if s.endswith("L") else "")
    return s
