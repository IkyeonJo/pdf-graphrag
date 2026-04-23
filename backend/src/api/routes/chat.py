from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.chat import answer_question

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    question: str


@router.post("/chat/{doc_id}")
async def chat(request: Request, doc_id: str, body: ChatRequest) -> dict:
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question is empty")

    llm = request.app.state.llm
    neo4j = request.app.state.neo4j
    try:
        result = await answer_question(
            body.question, doc_id, llm=llm, neo4j=neo4j
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return result.model_dump()
