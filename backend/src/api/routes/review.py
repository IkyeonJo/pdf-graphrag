from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.review import Decision, load_review, upsert_decision

router = APIRouter(tags=["review"])


class DecisionRequest(BaseModel):
    category: str
    entity_key: str
    decision: Decision
    note: str = ""
    decided_by: str = "engineer"


@router.get("/review/{doc_id}")
async def get_review(doc_id: str) -> dict:
    state = await load_review(doc_id)
    return state.model_dump()


@router.post("/review/{doc_id}")
async def post_decision(doc_id: str, body: DecisionRequest) -> dict:
    if not body.entity_key.strip():
        raise HTTPException(status_code=400, detail="entity_key is empty")
    state = await upsert_decision(
        doc_id=doc_id,
        category=body.category,
        entity_key=body.entity_key,
        decision=body.decision,
        note=body.note,
        decided_by=body.decided_by,
    )
    return state.model_dump()
