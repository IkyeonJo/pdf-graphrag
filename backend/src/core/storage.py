"""Simple JSON-file document store for MVP.

Holds ExtractionResult keyed by doc_id. Lives under /data/indexes/documents/.
Not intended for high concurrency — Phase 2 can swap for PostgreSQL if needed.
"""

import asyncio
import json
from pathlib import Path

from src.extraction.pipeline import ExtractionResult

_BASE_DIR = Path("/data/indexes/documents")
_LOCK = asyncio.Lock()


def _path_for(doc_id: str) -> Path:
    return _BASE_DIR / f"{doc_id}.json"


async def save(result: ExtractionResult) -> None:
    async with _LOCK:
        _BASE_DIR.mkdir(parents=True, exist_ok=True)
        _path_for(result.doc_id).write_text(
            result.model_dump_json(indent=2),
            encoding="utf-8",
        )


async def load(doc_id: str) -> ExtractionResult | None:
    path = _path_for(doc_id)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ExtractionResult.model_validate(raw)


async def list_docs() -> list[dict]:
    if not _BASE_DIR.exists():
        return []
    out: list[dict] = []
    for p in sorted(_BASE_DIR.glob("*.json")):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            out.append(
                {
                    "doc_id": raw.get("doc_id"),
                    "filename": raw.get("filename"),
                    "page_count": raw.get("page_count"),
                }
            )
        except Exception:
            continue
    return out
