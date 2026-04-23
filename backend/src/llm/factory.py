from src.core.config import settings
from src.llm.base import LLMClient
from src.llm.openai_client import OpenAIClient
from src.llm.vllm_client import VLLMClient


def get_llm_client() -> LLMClient:
    """환경변수 LLM_BACKEND에 따라 클라이언트 생성.

    LLM_BACKEND=openai  → OpenAIClient  (데모)
    LLM_BACKEND=vllm    → VLLMClient    (온프레미스 폐쇄망)
    """
    backend = settings.llm_backend.lower()

    if backend == "openai":
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    if backend == "vllm":
        return VLLMClient(
            base_url=settings.vllm_base_url,
            model=settings.vllm_model,
            api_key=settings.vllm_api_key,
        )
    raise ValueError(f"Unknown LLM_BACKEND: {settings.llm_backend}")
