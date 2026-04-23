"""Human-in-the-loop decisions per document.

Each review is a list of `ReviewDecision` keyed by (category, entity_key).
Persisted as /data/indexes/reviews/{doc_id}.json. Keeps the demo simple
while showing the shape of the auditable approval flow.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

_BASE_DIR = Path("/data/indexes/reviews")
_LOCK = asyncio.Lock()

Decision = Literal["approved", "rejected", "pending"]


class ReviewDecision(BaseModel):
    category: str        # items / standards / toxic_clauses / validation / ...
    entity_key: str      # deterministic key for this entity
    decision: Decision = "pending"
    note: str = ""
    decided_at: str = ""
    decided_by: str = ""


class ReviewState(BaseModel):
    doc_id: str
    decisions: list[ReviewDecision] = Field(default_factory=list)


def _path_for(doc_id: str) -> Path:
    return _BASE_DIR / f"{doc_id}.json"


async def load_review(doc_id: str) -> ReviewState:
    async with _LOCK:
        path = _path_for(doc_id)
        if not path.exists():
            return ReviewState(doc_id=doc_id)
        return ReviewState.model_validate_json(path.read_text(encoding="utf-8"))


async def _save(state: ReviewState) -> None:
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    _path_for(state.doc_id).write_text(
        state.model_dump_json(indent=2),
        encoding="utf-8",
    )


async def upsert_decision(
    doc_id: str,
    category: str,
    entity_key: str,
    decision: Decision,
    note: str = "",
    decided_by: str = "engineer",
) -> ReviewState:
    async with _LOCK:
        path = _path_for(doc_id)
        state = (
            ReviewState.model_validate_json(path.read_text(encoding="utf-8"))
            if path.exists()
            else ReviewState(doc_id=doc_id)
        )
        for d in state.decisions:
            if d.category == category and d.entity_key == entity_key:
                d.decision = decision
                d.note = note
                d.decided_at = datetime.now(timezone.utc).isoformat()
                d.decided_by = decided_by
                break
        else:
            state.decisions.append(
                ReviewDecision(
                    category=category,
                    entity_key=entity_key,
                    decision=decision,
                    note=note,
                    decided_at=datetime.now(timezone.utc).isoformat(),
                    decided_by=decided_by,
                )
            )
        await _save(state)
        return state


async def list_decisions(doc_id: str) -> list[ReviewDecision]:
    state = await load_review(doc_id)
    return state.decisions
