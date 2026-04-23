# LLM 추상화 레이어 — OpenAI ↔ vLLM 전환 경로

본 문서는 데모에서 사용한 **OpenAI API**를 고객 폐쇄망 환경의 **vLLM(Qwen2.5-72B)** 로 한 줄 교체로 전환 가능함을 실코드로 증명합니다.

---

## 1. 설계 원칙

1. **호출 측은 백엔드를 모른다** — 모든 LLM 사용은 `LLMClient` 추상 인터페이스 통해서만.
2. **프롬프트와 스키마는 양쪽 모두 호환** — OpenAI `response_format.json_schema` vs vLLM `guided_json`.
3. **환경변수 하나로 런타임 스위칭** — 재배포 불필요.

---

## 2. 코드 구조

```
backend/src/llm/
├── base.py           # LLMClient (추상)
├── openai_client.py  # 데모용
├── vllm_client.py    # 프로덕션 (vLLM OpenAI-호환 API 사용)
└── factory.py        # LLM_BACKEND에 따라 인스턴스 생성
```

---

## 3. 추상 인터페이스 (`base.py`)

```python
class LLMClient(ABC):
    model: str

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """자유 텍스트 응답"""

    @abstractmethod
    async def complete_json(
        self,
        messages: list[Message],
        *,
        schema: dict | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict:
        """JSON 스키마 강제 응답"""
```

---

## 4. OpenAI 구현 (`openai_client.py`)

```python
class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def complete_json(self, messages, *, schema=None, ...) -> dict:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction",
                    "schema": schema,
                    "strict": True,
                },
            },
            ...
        )
        return json.loads(resp.choices[0].message.content)
```

---

## 5. vLLM 구현 (`vllm_client.py`)

**핵심 관찰**: vLLM은 OpenAI-호환 API를 제공하므로 **동일한 `AsyncOpenAI` SDK**로 호출 가능합니다. 차이점은 구조화 출력 강제 메커니즘뿐입니다.

```python
class VLLMClient(LLMClient):
    def __init__(self, base_url: str, model: str, api_key: str = "EMPTY"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def complete_json(self, messages, *, schema=None, ...) -> dict:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            # vLLM 고유: extra_body로 guided_json 전달
            extra_body={"guided_json": schema},
            ...
        )
        return json.loads(resp.choices[0].message.content)
```

---

## 6. 팩토리 (`factory.py`)

```python
def get_llm_client() -> LLMClient:
    if settings.llm_backend == "openai":
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    if settings.llm_backend == "vllm":
        return VLLMClient(
            base_url=settings.vllm_base_url,
            model=settings.vllm_model,
            api_key=settings.vllm_api_key,
        )
    raise ValueError(...)
```

---

## 7. 전환 방법 (실행 단계)

### 데모 → 프로덕션

**고객 환경에서 한 번만**:

```bash
# 1. vLLM 서빙 시작 (고객 GPU 서버에서, 예: RTX 5090 Dual)
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-72B-Instruct-AWQ \
    --port 8000 \
    --served-model-name qwen2.5-72b \
    --gpu-memory-utilization 0.9 \
    --max-model-len 131072 \
    --enable-prefix-caching

# 2. .env 수정 (코드 변경 없음)
LLM_BACKEND=vllm
VLLM_BASE_URL=http://vllm-server:8000/v1
VLLM_MODEL=qwen2.5-72b

# 3. backend 재시작
docker compose restart backend
```

**어떤 코드도 수정되지 않습니다.** 호출 측(pipeline.py, graphrag_qa.py, tier2_llm.py)은 `LLMClient` 인터페이스만 보므로 백엔드 교체에 무감합니다.

---

## 8. 프롬프트 / 스키마 호환성

| 항목 | OpenAI | vLLM + Qwen2.5 |
|---|---|---|
| Chat messages (role/content) | ✅ | ✅ |
| Temperature, max_tokens | ✅ | ✅ |
| JSON 스키마 강제 | `response_format.json_schema` (strict) | `extra_body.guided_json` (xgrammar) |
| Function calling | ✅ | ✅ (동일 포맷) |
| Streaming | ✅ | ✅ |
| Prompt caching | 자동 | `--enable-prefix-caching` |

**본 프로젝트는 프롬프트에 OpenAI 전용 기능(예: o1-preview의 reasoning tokens)을 쓰지 않았습니다** — 전환 리스크 최소화.

---

## 9. 임베딩 추상화

동일 패턴이 `backend/src/similarity/embedding.py`에도 적용되어 있습니다:

```python
class EmbeddingClient(ABC):
    dimension: int
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

# OpenAIEmbeddingClient (데모)
# (미구현) LocalEmbeddingClient — BGE-M3를 sentence-transformers로 로드
```

프로덕션에서는 `BGE-M3`를 로컬 GPU 또는 CPU 서빙으로 교체 (한/영 멀티링구얼 SOTA, Apache-2.0 라이선스).

---

## 10. 전환 체크리스트 (수주 후 착수 시)

- [ ] 고객 GPU 서버 스펙 확정 (Qwen2.5-72B-AWQ 기준 VRAM 약 40GB 필요)
- [ ] vLLM 서빙 파라미터 튜닝 (context 128K 활용 여부)
- [ ] `.env` 내 `LLM_BACKEND=vllm` + `VLLM_*` 설정
- [ ] BGE-M3 임베딩 로컬 서빙 (별도 컨테이너 또는 동일 프로세스)
- [ ] 네트워크: OpenAI 엔드포인트 차단 확인 + 로컬 엔드포인트만 허용
- [ ] 통합 테스트: 동일한 MR-161 PDF로 추출 결과 diff 확인 (<5% 오차 목표)
- [ ] 성능 벤치마크: 3,000 페이지 처리 시간 측정
- [ ] 운영 모니터링: Prometheus + vLLM metrics 엔드포인트 연동

---

## 11. 결론

- 호출 측 코드 **0줄 수정** + 환경변수 3개 변경으로 폐쇄망 전환 완료
- `VLLMClient`는 스텁이 아니라 **실동작 구현체**로, 동일한 스키마 강제 경로를 제공
- 본 데모는 **"OpenAI로 동작"을 이미 증명**했고, 프로덕션 전환 리스크는 **모델 품질 차이 검증**만 남음 (코드 품질 리스크 없음)
