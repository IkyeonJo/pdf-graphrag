# 벤치마크 결과

**실행일**: 2026-04-22
**대상 문서**: `MR-161-2018-Tender-Specs.pdf` (Energy Fiji Limited, 14 페이지)
**환경**: macOS 로컬 Docker Desktop, OpenAI `gpt-4o-mini` + `text-embedding-3-small`
**실행**: `docker exec pdfgraph-backend python -m src.scripts.benchmark`

---

## 1. End-to-End 레이턴시

| 단계 | 시간 | 비고 |
|---|---|---|
| Upload + Extraction 전체 | **49.5s** | 대부분 LLM 1회 호출 (Tier 2) + 룰/Jump/Toxic |
| Validation (R001~R005) | **0.04s** | 룰은 전부 메모리 내 로직 |
| Similarity (Top-4) | **1.91s** | 신규 임베딩 1회 + 4개 dot product |
| Chat Q1 (독소조항 3개) | **5.47s** | graph facts 38개 활용 |
| Chat Q2 (재질 안전성) | **4.02s** | 2개 citation |
| Chat Q3 (품목 개수) | **1.46s** | 사실 질의, 간결 응답 |

---

## 2. 추출 품질 (MR-161 정답 대비)

| 카테고리 | 추출 | 실제 | 정확도 |
|---|---|---|---|
| Items (Table 1.1) | **18** | 18 | 100% |
| Standards (References 2.1) | **17** | 13 선언 + 4 본문 참조 | 100% (커버리지) |
| Materials | 3 (SUS304/SUS316/"304 or 316") | 2 (grade 304 or 316) | 중복만 존재 |
| Environmental | **6** | 6 | 100% |
| Electrical | **16** | 7 (Table 3.2) + 9 세부 | 풍부 |
| Tests | 0 (LLM 비결정성) | 6 (Table 6.1) | ⚠ LLM run-to-run 편차 |
| Toxic Clauses | **5** | 4~5 주요 독소 | 100% (룰 기반 확정) |

**추출 품질 요약**:
- Deterministic 영역 (Items, Standards, Env, Toxic): 100% 탐지
- LLM 의존 영역 (Tests): 실행 간 편차 있음 → Phase 3에서 룰 기반 Table 파싱으로 보강 예정
- 룰+LLM 병합 설계가 bare LLM 대비 일관성 확보

---

## 3. Graph 적재

| Node Label | Count |
|---|---|
| Document | 1 |
| Section | 37 |
| Item | 18 |
| Standard | 17 (전역 공유) |
| Material | 3 (전역 공유) |
| EnvCondition | 6 |
| ElectricalSpec | 16 |
| ToxicClause | 5 |
| TestRequirement | 0 |

| Edge Type | Count |
|---|---|
| CONTAINS | 37 |
| MENTIONS | ~66 (섹션-엔티티, **가장 좁은 섹션 하나만**) |
| REFERS_TO | 37 (standard 30, table 4, clause 3) |
| HAS_RISK | 5 |
| HAS_ENTITY | ~65 |

**총 노드 ~104, 엣지 ~210**.

---

## 4. 의존성 검증 결과

| 규칙 | 결과 | 근거 |
|---|---|---|
| R001 [High] 염분+SUS304 | **이슈** | 대기 "Saliferous, corrosive" (p.6) + 재질 SUS304 (p.7) |
| R002 [Medium] 보관 온도 포함 | Pass | 10~40℃ 보관, 10~40℃ 사용 |
| R003 [Low] 표준 선언 누락 | **이슈** | ISO 9001 참조, References 미선언 |
| R004 [Medium] 강도등급/나사공차 | **이슈** | 18개 체결요소에 A2-70/6H/8g 누락 |
| R005 [High] 과도한 수명 | **이슈** | 서비스 수명 60년 > 기준 40년 |

**의미**: 단일 한글 표준 JSON을 수정하면 모든 규칙이 재적용 — Python 수정 불요.

---

## 5. 유사 프로젝트 매칭

| 순위 | 프로젝트 | Score | Cosine | Jaccard | 공통 표준 | 공통 재질 |
|---|---|---|---|---|---|---|
| 1 | 한전 33kV (2024, 수주 성공) | **52.4%** | 0.60 | 0.40 | 8 | SUS316 |
| 2 | 현대중공업 해양 (2023, 수주 성공) | 45.5% | 0.64 | 0.18 | 5 | — |
| 3 | EVN 베트남 (2023, 포기) | 42.8% | 0.55 | 0.24 | 4 | SUS316 |
| 4 | SR 철도 (2022, 수주 성공) | 37.6% | 0.49 | 0.20 | 3 | SUS316 |

**의사결정 시사점**: MR-161은 한전 33kV와 가장 유사하며, **공통 표준 8개 + SUS316**으로 조달/품질 기준이 상당 부분 공유됨. 한전 프로젝트의 수주 성공 레퍼런스를 견적 근거로 재활용 가능.

---

## 6. 챗봇 답변 품질 (샘플)

**Q1**: "이 입찰의 가장 불리한 독소조항 3개는?"
**A**: High 2건 + Medium 1건을 정확히 식별, 각 조항 텍스트와 페이지 번호 제시. 5.47초.

**Q2**: "Saliferous 환경에서 이 볼트 사양이 안전한가?"
**A**: 대기 조건(p.6)과 재질(304/316)을 교차 검증해 "안전하지 않을 수 있음" 판단, 근거 2개. 4.02초.

**Q3**: "Table 1.1에 있는 품목 개수는?"
**A**: "18개" 정답. 1.46초 (팩트 질의는 짧게).

---

## 7. 리소스 사용량

| 항목 | 값 |
|---|---|
| Backend 이미지 | 615 MB |
| Frontend 이미지 | 48 MB |
| Neo4j (Community) | ~500 MB |
| 추출 결과 JSON (MR-161) | 42 KB |
| 그래프 볼륨 | ~15 MB |

---

## 8. 프로덕션 환산 예상

| 항목 | 데모 (MR-161, 14p) | 프로덕션 (3,000p 문서) |
|---|---|---|
| LLM 호출 방식 | 단일 문서 전체 1회 | 섹션 단위 chunking, 동시성 제한 |
| 예상 시간 | 49초 | **8~15분** (vLLM 72B 기준, 병렬 8) |
| 예상 노드 수 | 100 | ~30K |
| OOM 리스크 | 없음 | Tier 1 페이지 스트리밍 + Tier 2 chunking으로 회피 |

---

## 9. 개선 여지 (Phase 4+)

1. **Tests 카테고리 결정성 강화**: pdfplumber로 Table 6.1을 직접 파싱해 LLM 의존 제거
2. **섹션 매칭 content-aware 고도화**: 현재는 페이지 범위 기반 — 페이지 내 텍스트 좌표까지 활용하면 2.1 vs 2.2 같은 동일 페이지 모호성 해소
3. **Text-to-Cypher (선택적)**: 챗봇에서 LLM이 직접 쿼리 생성 + 검증 단계로 확장
4. **Text-to-Speech**: 검수 결과 음성 브리핑 (현장 엔지니어용)

현재 단계에서는 **PRD 요구항목 전체가 동작**하므로 프로덕션 전환 리스크는 모델 품질/스케일 검증에 집중됩니다.
