import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from src.core import storage
from src.extraction import run_pipeline
from src.graph import build_graph

router = APIRouter(tags=["upload"])

UPLOAD_DIR = Path("/data/uploads")


@router.post("/upload")
async def upload_pdf(request: Request, file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4().hex[:12]
    saved_path = UPLOAD_DIR / f"{doc_id}_{file.filename}"
    content = await file.read()
    saved_path.write_bytes(content)

    llm = request.app.state.llm
    neo4j_client = request.app.state.neo4j

    result = await run_pipeline(saved_path, doc_id=doc_id, llm=llm)
    await storage.save(result)
    graph_stats = await build_graph(neo4j_client, result)

    return {
        "doc_id": result.doc_id,
        "filename": result.filename,
        "page_count": result.page_count,
        "sections": len(result.sections),
        "tables": len(result.tables),
        "rule_hits": len(result.rule_hits),
        "graph_stats": graph_stats,
    }
