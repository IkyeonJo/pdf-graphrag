from fastapi import APIRouter, HTTPException

from src.core import storage

router = APIRouter(tags=["extraction"])


@router.get("/documents")
async def list_documents() -> list[dict]:
    return await storage.list_docs()


@router.get("/extraction/{doc_id}")
async def get_extraction(doc_id: str) -> dict:
    result = await storage.load(doc_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return result.model_dump()
