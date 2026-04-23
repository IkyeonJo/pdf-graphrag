"""LLM 추상 인터페이스.

데모는 OpenAI API, 프로덕션(폐쇄망)은 vLLM으로 전환.
vLLM은 OpenAI 호환 API를 제공하므로 두 구현체는 대부분 공유 가능하지만,
base를 통해 호출 측이 백엔드에 무관해지도록 분리한다.
"""

from abc import ABC, abstractmethod
from typing import Any, Literal, TypedDict


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMClient(ABC):
    """LLM 호출을 백엔드 비종속으로 추상화."""

    model: str

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """자유 형식 텍스트 응답."""

    @abstractmethod
    async def complete_json(
        self,
        messages: list[Message],
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """JSON 스키마를 강제한 구조화 응답.

        schema가 주어지면 JSON Schema로 강제(지원 시),
        미지원 백엔드에서는 프롬프트 레벨 지시 + 파싱 fallback.
        """

    async def close(self) -> None:
        """리소스 정리가 필요한 구현체를 위한 훅."""
        return None
