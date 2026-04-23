"""Embedding abstraction.

OpenAI `text-embedding-3-small` for the demo. A local BGE-M3 client can
slot in behind the same interface for on-premise deployments.
"""

from abc import ABC, abstractmethod

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import settings


class EmbeddingClient(ABC):
    dimension: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def close(self) -> None:
        return None


class OpenAIEmbeddingClient(EmbeddingClient):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.model = model
        self.dimension = 1536 if model == "text-embedding-3-small" else 3072
        self._client = AsyncOpenAI(api_key=api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    async def close(self) -> None:
        await self._client.close()


def get_embedding_client() -> EmbeddingClient:
    # For now OpenAI only. Mirror the LLM factory pattern when local embeddings land.
    return OpenAIEmbeddingClient(api_key=settings.openai_api_key)
