"""vLLM 클라이언트 (프로덕션 전환용).

vLLM은 OpenAI 호환 API를 제공하므로 AsyncOpenAI를 그대로 재사용하되
base_url만 vLLM 서버로 지정한다. 한 줄 교체로 폐쇄망 전환 가능함을
코드로 증명하는 것이 이 모듈의 존재 이유.
"""

import json
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.llm.base import LLMClient, Message


class VLLMClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "EMPTY",
    ):
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def complete_json(
        self,
        messages: list[Message],
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # vLLM supports guided_json via extra_body for structured decoding.
        if schema is not None:
            kwargs["extra_body"] = {"guided_json": schema}
        else:
            kwargs["response_format"] = {"type": "json_object"}

        resp = await self._client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

    async def close(self) -> None:
        await self._client.close()
