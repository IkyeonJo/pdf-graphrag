"""15 category schema for structured extraction.

Aligned with client PRD's "15 major categories" requirement.
Each category is a list of entities so LLM output is uniform and Neo4j-friendly.
"""

from pydantic import BaseModel, Field

CATEGORY_KEYS = [
    "items",          # 품목 (Table 1.1)
    "materials",      # 재질
    "dimensions",     # 치수/공차
    "environmental",  # 환경 조건
    "electrical",     # 전기 사양
    "standards",      # 외부 표준 참조 (AS, ISO, IEC, KS)
    "tests",          # 시험 (Type/Batch/Routine/Acceptance)
    "marking",        # 마킹/식별
    "packaging",      # 포장
    "storage",        # 보관
    "lifespan",       # 수명/신뢰성
    "samples",        # 샘플 제공
    "training",       # 교육
    "delivery",       # 납품/문서 제출
    "toxic_clauses",  # 독소조항 (Phase 1은 흔적만, Phase 3에 본격 탐지)
]


class Item(BaseModel):
    stock_code: str = ""
    description: str
    page: int | None = None


class Material(BaseModel):
    grade: str
    standard: str = ""
    page: int | None = None


class Dimension(BaseModel):
    subject: str
    value: str
    unit: str = ""
    page: int | None = None


class EnvCondition(BaseModel):
    type: str  # "Temperature Peak", "Humidity", "Atmosphere", ...
    value: str
    unit: str = ""
    page: int | None = None


class ElectricalSpec(BaseModel):
    type: str  # "Nominal Voltage", "System Frequency", ...
    value: str
    unit: str = ""
    page: int | None = None


class StandardRef(BaseModel):
    code: str   # "AS 1111"
    title: str = ""
    page: int | None = None


class TestRequirement(BaseModel):
    category: str  # "Type Test" | "Batch Test" | "Routine Test" | "Acceptance Test"
    criterion: str
    reference: str = ""
    page: int | None = None


class FreeFormEntry(BaseModel):
    description: str
    page: int | None = None


class ToxicClause(BaseModel):
    text: str
    severity: str = "Medium"  # "High" | "Medium" | "Low"
    reason: str = ""
    page: int | None = None


class ExtractedDocument(BaseModel):
    """15 category payload. Each list may be empty but must exist."""

    items: list[Item] = Field(default_factory=list)
    materials: list[Material] = Field(default_factory=list)
    dimensions: list[Dimension] = Field(default_factory=list)
    environmental: list[EnvCondition] = Field(default_factory=list)
    electrical: list[ElectricalSpec] = Field(default_factory=list)
    standards: list[StandardRef] = Field(default_factory=list)
    tests: list[TestRequirement] = Field(default_factory=list)
    marking: list[FreeFormEntry] = Field(default_factory=list)
    packaging: list[FreeFormEntry] = Field(default_factory=list)
    storage: list[FreeFormEntry] = Field(default_factory=list)
    lifespan: list[FreeFormEntry] = Field(default_factory=list)
    samples: list[FreeFormEntry] = Field(default_factory=list)
    training: list[FreeFormEntry] = Field(default_factory=list)
    delivery: list[FreeFormEntry] = Field(default_factory=list)
    toxic_clauses: list[ToxicClause] = Field(default_factory=list)


def llm_json_schema() -> dict:
    """JSON schema for ExtractedDocument, OpenAI structured output / vLLM guided_json compatible."""
    schema = ExtractedDocument.model_json_schema()
    # OpenAI strict mode requires additionalProperties:false on all objects and all keys in required.
    _enforce_strict(schema)
    return schema


def _enforce_strict(node: dict) -> None:
    if not isinstance(node, dict):
        return
    # OpenAI strict JSON schema disallows "default" at any level.
    node.pop("default", None)
    if node.get("type") == "object" and "properties" in node:
        node["additionalProperties"] = False
        node["required"] = list(node["properties"].keys())
        for v in node["properties"].values():
            _enforce_strict(v)
    for key in ("items", "anyOf", "allOf", "oneOf"):
        if key in node:
            sub = node[key]
            if isinstance(sub, list):
                for s in sub:
                    _enforce_strict(s)
            else:
                _enforce_strict(sub)
    if "$defs" in node:
        for s in node["$defs"].values():
            _enforce_strict(s)
