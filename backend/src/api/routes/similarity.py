from fastapi import APIRouter, HTTPException, Request

from src.similarity import run_matching

router = APIRouter(tags=["similarity"])


@router.get("/similarity/{doc_id}")
async def get_similarity(request: Request, doc_id: str, top_k: int = 3) -> dict:
    embedder = request.app.state.embedder
    try:
        report = await run_matching(doc_id, embedder, top_k=top_k)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return report.model_dump()
