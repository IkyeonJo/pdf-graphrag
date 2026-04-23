from fastapi import APIRouter, HTTPException

from src.validation import run_validation

router = APIRouter(tags=["validation"])


@router.get("/validation/{doc_id}")
async def get_validation(doc_id: str) -> dict:
    try:
        report = await run_validation(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return report.model_dump()
