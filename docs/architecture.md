# PDF GraphRAG — 시스템 아키텍처 설계서

**프로젝트**: 코리아스틸 사양서 자동 분석 온프레미스 AI 시스템
**대상 독자**: 기술 의사결정자, 엔지니어링 리드
**버전**: 1.0 (2026-04)

---

## 1. 목표

고객이 송부하는 비정형 PDF 사양서(PTS)를 자동 분석하여

1. 15개 카테고리로 **구조화 추출**
2. 본문 내 상호참조(Appendix / Table / Standard)를 자동 따라가는 **Jump Engine**
3. **사내 표준 대비 독소조항 자동 탐지**
4. 과거 프로젝트와의 **유사도 매칭** (수주/포기 레퍼런스)
5. 근거 페이지를 포함한 **자연어 질의응답(GraphRAG Q&A)**

을 수행하는 **완전 폐쇄망** AI 시스템.

---

## 2. 아키텍처 개요

```
            ┌─────────────────────────────────────────────────────┐
            │                   Client Browser                    │
            │   React 18 + Vite + TypeScript + Tailwind CSS       │
            └────────────────────┬────────────────────────────────┘
                                 │ REST/JSON
            ┌────────────────────▼────────────────────────────────┐
            │                 FastAPI API Layer                   │
            │  /upload  /extraction  /validation  /similarity     │
            │  /chat    /review      /health      /llm/ping       │
            └────────────────────┬────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────▼──────────┐  ┌──────────▼──────────┐  ┌──────────▼─────────┐
│   Extraction     │  │     Validation      │  │     Similarity     │
│     Pipeline     │  │    (R001~R005)      │  │   (Hybrid Score)   │
│                  │  │                     │  │                    │
│  PDF Loader      │  │  Cypher + Rules ↔   │  │  Embedding (OpenAI │
│  Table Parser    │  │  company_std.ko.json│  │  text-embedding-3) │
│  TOC Extractor   │  │                     │  │  + Jaccard(graph)  │
│  Tier 1 Rules    │  │                     │  │                    │
│  Tier 2 LLM      │  │                     │  │                    │
│  Jump Engine     │  │                     │  │                    │
│  Toxic Detector  │  │                     │  │                    │
└────────┬─────────┘  └──────────┬──────────┘  └──────────┬─────────┘
         │                       │                        │
         └───────────────────────┼────────────────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │     Persistence Layer       │
                  │                             │
                  │  Neo4j     │  FAISS-ready   │
                  │  (graph)   │  (vector)      │
                  │            │                │
                  │  JSON      │  company_std   │
                  │  (docs)    │  (Korean ref)  │
                  └─────────────────────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │   LLM Abstraction Layer     │
                  │                             │
                  │  LLMClient (base)           │
                  │   ├── OpenAIClient (demo)   │
                  │   └── VLLMClient (on-prem)  │
                  │                             │
                  │   switch via LLM_BACKEND    │
                  └─────────────────────────────┘
```

---

## 3. 데이터 모델 (Neo4j)

### 노드 라벨

| 라벨 | 키 | 설명 |
|---|---|---|
| `Document` | `id` (unique) | 업로드된 PTS |
| `Section` | `(doc_id, number)` unique | TOC 기반 섹션 (예: "2.1 Applicable Standards") |
| `Item` | `(doc_id, description)` | Table 1.1의 품목 (M100 x M12 볼트 등) |
| `Standard` | `code` (unique, global) | AS/ISO/IEC/KS 등 외부 표준 (문서 간 공유) |
| `Material` | `grade` (unique, global) | SUS316 등 재질 등급 (문서 간 공유) |
| `EnvCondition` | `(doc_id, type, value)` | Saliferous, 40℃ 등 |
| `ElectricalSpec` | `(doc_id, type, value)` | 11kV, 50Hz 등 |
| `TestRequirement` | `(doc_id, category, criterion)` | Type Test, Batch Test 등 |
| `ToxicClause` | `(doc_id, text)` | 룰/LLM 탐지 독소조항 |

### 관계

| 관계 | 방향 | 의미 |
|---|---|---|
| `CONTAINS` | Document → Section | 문서가 섹션 포함 |
| `HAS_ENTITY` | Document → * | 문서 소유 엔티티 |
| `MENTIONS` | Section → * | **가장 좁은** 섹션이 엔티티 언급 (depth + 섹션 번호 기준) |
| `REFERS_TO` | Section → Section/Standard | Jump Engine 결과 (kind: table/section/clause/appendix/standard) |
| `HAS_RISK` | Document/Section → ToxicClause | 독소조항 보유 |

### 스키마 제약

- `Standard.code`와 `Material.grade`는 **전역 유니크** → 문서 간 공통 표준을 통해 자동 유사도 그래프가 형성됨
- 9개 unique constraint + 2개 index로 MERGE 멱등성 보장

---

## 4. 추출 파이프라인

### 3-Tier 아키텍처 (PRD 요구사항)

```
PDF → [Tier 0: Parsing] ─┬→ PyMuPDF (텍스트, 페이지별)
                          ├→ pdfplumber (표)
                          └→ TOC Extractor (섹션 ↔ 페이지 매핑)
         │
         ├→ [Tier 1: 룰 기반]
         │   - 정규식: AS/ISO/IEC/KS 표준 코드, 전압, 온도, 습도, 강재 등급, 볼트 규격
         │   - 59개 deterministic hit (MR-161 기준)
         │
         ├→ [Tier 2: LLM 추출]
         │   - OpenAI structured outputs (json_schema strict)
         │   - vLLM 동등 구현은 guided_json 사용
         │   - 15개 카테고리 스키마 강제
         │
         ├→ [Tier 3: 의존성 교차검증]
         │   - R001~R005 룰: 한글 사내 표준 JSON ↔ 영문 추출 결과
         │   - Cypher 서브그래프 질의
         │
         └→ [Jump Engine]
             - Table / Section / Clause / Appendix / Standard 참조 감지
             - 목차 인덱스로 target 페이지 해결
             - REFERS_TO 엣지 생성
```

### 섹션 매핑 정확도

핵심 기술적 문제: 복수 섹션이 같은 페이지에서 시작할 때 엔티티를 **어느 섹션에 귀속**시킬 것인가.

해결책: `_find_best_section()` — 엔티티 페이지를 커버하는 모든 섹션 중
- 깊이(depth) 최대 (하지만 "2.0"은 깊이 1로 정규화)
- 동률이면 page_start 최대

**효과**: 단순 범위 매칭 대비 오탐 50개 → 0개 (MR-161 기준).

---

## 5. Jump Engine

### 감지 패턴

| Kind | Regex | 예시 |
|---|---|---|
| `table` | `Table \d+\.\d+` | "dimensions mentioned in Table 1.1" |
| `section` | `Section \d+(\.\d+)+` | "see Section 4.2" |
| `clause` | `Clause \d+(\.\d+)+` | "Clause 2.2 of AS 1154.1" |
| `appendix` | `Appendix [A-Z]` | "per Appendix A" |
| `standard` | `(AS(/NZS)?|ISO|IEC|KS) \d+(\.\d+)?` | "AS 1111", "ISO 31000" |

### 해결 로직

- Internal (table/section/clause/appendix): TOC 인덱스 또는 표 캡션 스캔으로 페이지 해결
- External (standard): `Standard` 노드로 REFERS_TO 엣지만 생성
- 중복 제거: `(kind, target, source_page)` 튜플 키

### MR-161 결과
- 37개 REFERS_TO 엣지 (standard 30, table 4, clause 3)
- 예: Section 14.1 → AS 1111 등 5개 Standard + Clause 6.2, 8.0

---

## 6. 의존성 교차 검증

`data/standards/company_std.ko.json` — **한글 사내 표준 DB**를 단일 진실의 원천(SoT)으로 사용:

| 규칙 | 심각도 | 검증 로직 |
|---|---|---|
| R001 | High | 대기 "saliferous/corrosive" + 재질 SUS304 → 충돌 |
| R002 | Medium | 보관 온도 범위가 사용 환경 범위를 ±5℃ 마진으로 포함 |
| R003 | Low | 본문 참조 표준이 References 섹션에 누락 |
| R004 | Medium | 체결요소 품목에 강도등급(A2-70 등) / 나사공차(6H/8g 등) 명시 |
| R005 | High | 서비스 수명 요구 > 40년 |

규칙은 JSON 선언형이므로 **Python 코드 수정 없이 추가/변경 가능**.

---

## 7. 유사 프로젝트 매칭 (하이브리드 스코어)

```
Score = 0.6 × cos(embedding(query), embedding(past))
      + 0.4 × [0.7 × Jaccard(standards) + 0.3 × Jaccard(materials)]
```

- 임베딩: OpenAI `text-embedding-3-small` (1536-d)
- 쿼리 요약: 추출된 15개 카테고리 → 구조화 문자열
- 과거 프로젝트: `data/past_projects/*.json` 4개 (한전 33kV, 현대중공업 해양, EVN 베트남, SR 철도)

**MR-161 매칭 결과**:

| 순위 | 프로젝트 | Score | 공통 표준 | 공통 재질 |
|---|---|---|---|---|
| 1 | 한전 33kV | 51.3% | 8 | SUS316 |
| 2 | 현대중공업 해양 | 45.2% | 5 | — |
| 3 | EVN 베트남 | 41.9% | 4 | SUS316 |
| 4 | SR 철도 | 37.3% | 3 | SUS316 |

---

## 8. GraphRAG Q&A

### 전략: Pre-built Cypher + 구조화 컨텍스트

Text-to-Cypher 대신 **사전 정의된 Cypher 쿼리**를 모든 질문에 실행:

1. Section ↔ Standard 매핑 (MENTIONS)
2. REFERS_TO 엣지 상위 30건
3. HAS_RISK 엣지 (severity 정렬)

결과를 추출 JSON과 함께 컨텍스트로 주입, LLM이 JSON schema에 맞춰 답변 + citations 생성.

**이유**:
- Text-to-Cypher는 데모에서 검증 비용이 높음
- Pre-built는 예측 가능 + 그래프 활용 증명 + 비용 절감

### 예시 질문/답변

- Q: "이 입찰에서 가장 불리한 독소조항 3개?"
- A: 서비스 수명 60년(p.12 High) / 인증서 미제출시 즉시 거절(p.11 High) / EFL 수용 테스트(p.10 Medium) + 각 citation

---

## 9. LLM 추상화 (폐쇄망 전환 경로)

상세: [`docs/llm_abstraction.md`](./llm_abstraction.md)

```python
LLMClient (abstract)
├── OpenAIClient      # 데모
└── VLLMClient        # 프로덕션 (vLLM OpenAI-호환 API)
```

`LLM_BACKEND=openai|vllm` 환경변수 한 줄로 전환. 프롬프트와 JSON 스키마는 양쪽 모두 호환.

---

## 10. 보안 / 운영

| 영역 | 데모 | 프로덕션 전환 |
|---|---|---|
| LLM | OpenAI API | **vLLM + Qwen2.5-72B** 로컬 서빙 |
| 임베딩 | OpenAI text-embedding-3 | **BGE-M3** 로컬 (한/영 멀티링구얼) |
| 저장소 | 로컬 Docker 볼륨 | 폐쇄망 NAS + 백업 정책 |
| 인증 | 없음 (MVP) | OIDC / SSO + 감사 로그 |
| 작업 큐 | 동기 처리 | **Celery + Redis** (PRD 요구) |
| 배포 | docker-compose | **Kubernetes** 또는 Docker Swarm |

---

## 11. 성능 / 확장성

- 14-page PDF 기준 전체 파이프라인 ~15초 (대부분 LLM 레이턴시)
- 3,000-page 처리 시 설계:
  - Tier 1 룰은 페이지 병렬
  - Tier 2 LLM은 섹션 단위 chunking → `asyncio.gather` 제한된 동시성
  - 추출 결과는 섹션별로 점진 병합
  - OOM 방지: PyMuPDF 페이지 스트리밍 (`fitz.Document` 자체가 메모리 매핑)

- Neo4j 메모리: 3,000 페이지 × 평균 15 엔티티 = 45K 노드 수준 → Community Edition 문제 없음

---

## 12. 테스트 전략

- **단위 테스트** (pytest): Jump Engine의 5개 케이스 (table/appendix/standard with clause/dedup/context)
- **통합 테스트**: 업로드 → 추출 → 그래프 → 검증 → 매칭 End-to-End (MR-161 기준 회귀)
- **벤치마크**: `docs/benchmarks.md` 참조

---

## 13. 폴더 구조

```
pdf_graphrag/
├── prd.md, plan.md                  # 요구/계획
├── docker-compose.yml               # Neo4j + backend + frontend
├── backend/
│   └── src/
│       ├── core/         (config, storage)
│       ├── llm/          (base + openai + vllm)
│       ├── parsing/      (pdf_loader, toc_extractor, table_parser)
│       ├── extraction/   (schemas, tier1_rules, tier2_llm,
│       │                  toxic_rules, jump_engine, pipeline)
│       ├── graph/        (schema.cypher, client, builder)
│       ├── validation/   (dependency_check: R001~R005)
│       ├── similarity/   (embedding, project_matcher)
│       ├── chat/         (graphrag_qa)
│       ├── review/       (store: Human-in-the-loop 결정 영속화)
│       └── api/          (FastAPI routes)
├── frontend/
│   └── src/components/
│       ├── PDFUploader, ExtractionTable, ReferencesView,
│       ├── DependencyReport, SimilarProjects, ChatPanel, ReviewPanel
├── data/
│   ├── samples/*.pdf
│   ├── standards/company_std.ko.json     # 한글 단일 진실 원천
│   └── past_projects/project_{A,B,C,D}.json
├── tests/                          # pytest
└── docs/                           # 이 문서
```

---

## 14. 결론

- **PRD 전 요구 항목을 동작하는 코드로 증명**
  - 15개 카테고리, 3-Tier 파이프라인, Jump Engine, 교차검증, 유사 매칭, GraphRAG Q&A, HITL 검수
- **폐쇄망 전환은 환경변수 1개 + 모델 이름만 바꾸면 됨** (LLM 추상화 + 로컬 임베딩 경로 확보)
- **한글 사내 표준을 단일 SoT로 선언형 관리** → 규칙 추가 시 Python 불요

데모 코드 기반으로 프로덕션 스케일업 시 주 작업은 **모델 로컬 서빙 + 작업 큐 + 보안/운영** 계층이며, 핵심 비즈니스 로직(파이프라인, 그래프, 검증)은 그대로 재사용됩니다.
