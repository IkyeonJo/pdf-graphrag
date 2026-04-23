"""Hybrid similarity: vector + graph overlap.

Score = 0.6 * cosine(embedding(query), embedding(past))
      + 0.4 * jaccard(graph_entities(query), graph_entities(past))

Past projects live in /data/past_projects/*.json.
Embeddings computed once on-demand and cached in memory.
"""

import asyncio
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel

from src.core.storage import load as load_extraction
from src.extraction.pipeline import ExtractionResult
from src.similarity.embedding import EmbeddingClient

_PROJECTS_DIR = Path("/data/past_projects")


@dataclass
class PastProject:
    id: str
    title: str
    client: str
    year: int
    outcome: str
    scale: str
    description: str
    standards: set[str] = field(default_factory=set)
    materials: set[str] = field(default_factory=set)
    summary_text: str = ""
    raw: dict = field(default_factory=dict)
    embedding: list[float] | None = None


class MatchedProject(BaseModel):
    id: str
    title: str
    client: str
    year: int
    outcome: str
    scale: str
    score: float            # hybrid, 0~1
    cosine: float
    jaccard: float
    shared_standards: list[str]
    shared_materials: list[str]


class SimilarityReport(BaseModel):
    doc_id: str
    matches: list[MatchedProject]
    query_summary: str


class _Store:
    def __init__(self) -> None:
        self._projects: list[PastProject] = []
        self._lock = asyncio.Lock()
        self._embedded = False

    def _load_projects(self) -> list[PastProject]:
        if not _PROJECTS_DIR.exists():
            return []
        out: list[PastProject] = []
        for path in sorted(_PROJECTS_DIR.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            summary = _project_summary_text(raw)
            out.append(
                PastProject(
                    id=raw["id"],
                    title=raw["title"],
                    client=raw.get("client", ""),
                    year=raw.get("year", 0),
                    outcome=raw.get("outcome", ""),
                    scale=raw.get("scale", ""),
                    description=raw.get("description", ""),
                    standards={s.upper() for s in raw.get("standards", [])},
                    materials={m.upper() for m in raw.get("materials", [])},
                    summary_text=summary,
                    raw=raw,
                )
            )
        return out

    async def ensure_embedded(self, embedder: EmbeddingClient) -> list[PastProject]:
        async with self._lock:
            if not self._projects:
                self._projects = self._load_projects()
            if self._embedded or not self._projects:
                return self._projects
            embeddings = await embedder.embed([p.summary_text for p in self._projects])
            for proj, emb in zip(self._projects, embeddings, strict=True):
                proj.embedding = emb
            self._embedded = True
            return self._projects


_store = _Store()


def get_project_store() -> _Store:
    return _store


def _project_summary_text(raw: dict) -> str:
    env = raw.get("environmental", {})
    elec = raw.get("electrical", {})
    return (
        f"Title: {raw.get('title','')}\n"
        f"Client: {raw.get('client','')} ({raw.get('year','')})\n"
        f"Scale: {raw.get('scale','')}\n"
        f"Description: {raw.get('description','')}\n"
        f"Standards: {', '.join(raw.get('standards', []))}\n"
        f"Materials: {', '.join(raw.get('materials', []))}\n"
        f"Atmosphere: {env.get('atmosphere','')}\n"
        f"Ambient: {env.get('ambient_temp_min_c','?')}~{env.get('ambient_temp_peak_c','?')}℃, "
        f"humidity {env.get('humidity_pct','?')}%\n"
        f"Voltage (kV): {elec.get('voltage_kv', [])}, "
        f"Frequency: {elec.get('frequency_hz','?')}Hz\n"
        f"Items: {raw.get('items_summary','')}\n"
        f"Tests: {', '.join(raw.get('tests', []))}\n"
        f"Service life: {raw.get('service_life_years','?')} years\n"
        f"Notes: {raw.get('notes','')}\n"
    )


def _query_summary_text(extraction: ExtractionResult) -> str:
    ex = extraction.extracted
    parts = [
        f"Title: {extraction.filename}",
        f"Pages: {extraction.page_count}",
        f"Standards: {', '.join(s.code for s in ex.standards)}",
        f"Materials: {', '.join(m.grade for m in ex.materials)}",
        f"Atmosphere / Temp / Humidity: "
        + "; ".join(f"{e.type}={e.value}" for e in ex.environmental),
        f"Electrical: "
        + "; ".join(f"{e.type}={e.value}" for e in ex.electrical),
        f"Items: "
        + "; ".join(it.description for it in ex.items[:10]),
        f"Tests: "
        + "; ".join(f"{t.category}:{t.criterion}" for t in ex.tests),
        f"Lifespan: "
        + "; ".join(l.description for l in ex.lifespan[:3]),
    ]
    return "\n".join(parts)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


async def run_matching(
    doc_id: str,
    embedder: EmbeddingClient,
    top_k: int = 3,
) -> SimilarityReport:
    extraction = await load_extraction(doc_id)
    if extraction is None:
        raise KeyError(f"doc {doc_id} not found")

    projects = await _store.ensure_embedded(embedder)
    if not projects:
        return SimilarityReport(
            doc_id=doc_id, matches=[], query_summary="(no past projects)"
        )

    query_text = _query_summary_text(extraction)
    [query_vec] = await embedder.embed([query_text])

    ex = extraction.extracted
    # Normalize codes for comparison
    query_standards = {
        _normalize_std(s.code) for s in ex.standards if s.code.strip()
    }
    query_materials = {m.grade.upper() for m in ex.materials if m.grade.strip()}

    scored: list[MatchedProject] = []
    for proj in projects:
        if proj.embedding is None:
            continue
        proj_standards_norm = {_normalize_std(s) for s in proj.standards}
        cos = _cosine(query_vec, proj.embedding)
        jac_std = _jaccard(query_standards, proj_standards_norm)
        jac_mat = _jaccard(query_materials, proj.materials)
        jac = 0.7 * jac_std + 0.3 * jac_mat
        hybrid = 0.6 * cos + 0.4 * jac
        shared_std = sorted(query_standards & proj_standards_norm)
        shared_mat = sorted(query_materials & proj.materials)
        scored.append(
            MatchedProject(
                id=proj.id,
                title=proj.title,
                client=proj.client,
                year=proj.year,
                outcome=proj.outcome,
                scale=proj.scale,
                score=round(hybrid, 4),
                cosine=round(cos, 4),
                jaccard=round(jac, 4),
                shared_standards=shared_std,
                shared_materials=shared_mat,
            )
        )

    scored.sort(key=lambda m: m.score, reverse=True)
    return SimilarityReport(
        doc_id=doc_id, matches=scored[:top_k], query_summary=query_text
    )


def _normalize_std(code: str) -> str:
    """'AS 1154.1' → 'AS 1154'. Treats sub-clause suffixes as the parent standard."""
    s = code.upper().strip()
    # collapse whitespace
    s = " ".join(s.split())
    # strip trailing sub-clause like '.1'
    if "." in s:
        head, tail = s.rsplit(".", 1)
        if tail.isdigit():
            return head
    return s
