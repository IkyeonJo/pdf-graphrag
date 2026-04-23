from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat as chat_routes
from src.api.routes import extraction as extraction_routes
from src.api.routes import review as review_routes
from src.api.routes import similarity as similarity_routes
from src.api.routes import upload as upload_routes
from src.api.routes import validation as validation_routes
from src.core.config import settings
from src.graph import get_neo4j_client
from src.llm import get_llm_client
from src.llm.base import LLMClient
from src.similarity.embedding import get_embedding_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    llm: LLMClient = get_llm_client()
    neo4j = get_neo4j_client()
    embedder = get_embedding_client()
    await neo4j.ensure_schema()

    app.state.llm = llm
    app.state.neo4j = neo4j
    app.state.embedder = embedder
    try:
        yield
    finally:
        await llm.close()
        await neo4j.close()
        await embedder.close()


app = FastAPI(
    title="PDF GraphRAG API",
    version="0.1.0",
    description=f"{settings.company_name} 사양서 자동 분석 시스템",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_routes.router)
app.include_router(extraction_routes.router)
app.include_router(validation_routes.router)
app.include_router(similarity_routes.router)
app.include_router(chat_routes.router)
app.include_router(review_routes.router)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "company": settings.company_name,
        "llm_backend": settings.llm_backend,
        "llm_model": app.state.llm.model,
    }


@app.get("/llm/ping")
async def llm_ping() -> dict[str, str]:
    client: LLMClient = app.state.llm
    reply = await client.complete(
        [
            {"role": "system", "content": "You reply with exactly one word."},
            {"role": "user", "content": "Say pong"},
        ],
        max_tokens=10,
    )
    return {"reply": reply.strip()}
