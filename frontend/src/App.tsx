import { useEffect, useState } from "react";
import {
  api,
  type DocumentListItem,
  type ExtractionResponse,
  type HealthResponse,
  type SimilarityReport,
  type UploadResponse,
  type ValidationReport,
} from "./api/client";
import { ChatPanel } from "./components/ChatPanel";
import { DependencyReport } from "./components/DependencyReport";
import { ExtractionTable } from "./components/ExtractionTable";
import { PDFUploader } from "./components/PDFUploader";
import { ReferencesView } from "./components/ReferencesView";
import { ReviewPanel } from "./components/ReviewPanel";
import { SimilarProjects } from "./components/SimilarProjects";

type Tab =
  | "extraction"
  | "references"
  | "validation"
  | "similarity"
  | "chat"
  | "review";

const TABS: { key: Tab; label: string }[] = [
  { key: "extraction", label: "추출 결과" },
  { key: "references", label: "Jump Engine" },
  { key: "validation", label: "의존성 검증" },
  { key: "similarity", label: "유사 프로젝트" },
  { key: "chat", label: "챗봇 Q&A" },
  { key: "review", label: "검수" },
];

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [currentDocId, setCurrentDocId] = useState<string | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [similarity, setSimilarity] = useState<SimilarityReport | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("extraction");
  const [loadingTab, setLoadingTab] = useState<Tab | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(String(e)));
    refreshDocs();
  }, []);

  async function refreshDocs() {
    try {
      const list = await api.listDocuments();
      setDocs(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function openDoc(docId: string) {
    setError("");
    setExtraction(null);
    setValidation(null);
    setSimilarity(null);
    setCurrentDocId(docId);
    try {
      const res = await api.getExtraction(docId);
      setExtraction(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    if (!currentDocId) return;
    if (activeTab === "validation" && !validation) {
      setLoadingTab("validation");
      api
        .getValidation(currentDocId)
        .then(setValidation)
        .catch((e) => setError(String(e)))
        .finally(() => setLoadingTab(null));
    }
    if (activeTab === "similarity" && !similarity) {
      setLoadingTab("similarity");
      api
        .getSimilarity(currentDocId, 4)
        .then(setSimilarity)
        .catch((e) => setError(String(e)))
        .finally(() => setLoadingTab(null));
    }
  }, [activeTab, currentDocId, validation, similarity]);

  async function handleUploaded(res: UploadResponse) {
    setUploadResult(res);
    await refreshDocs();
    await openDoc(res.doc_id);
  }

  return (
    <div className="min-h-screen p-8">
      <header className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            {health?.company ?? "코리아스틸"} · PDF GraphRAG
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            사양서 자동 분석 시스템 — 15개 카테고리 추출 · Jump Engine · 의존성
            검증 · 유사 프로젝트 매칭
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600 shadow-sm">
          <div>
            Backend:{" "}
            <span className="font-mono">
              {health?.status ?? (error ? "error" : "…")}
            </span>
          </div>
          <div>
            LLM:{" "}
            <span className="font-mono">
              {health?.llm_backend ?? "-"} / {health?.llm_model ?? "-"}
            </span>
          </div>
        </div>
      </header>

      <section className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-4">
          <PDFUploader onUploaded={handleUploaded} />

          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">
              분석된 문서 ({docs.length})
            </h2>
            {docs.length === 0 ? (
              <p className="text-xs text-slate-400">
                아직 업로드된 문서가 없습니다.
              </p>
            ) : (
              <ul className="space-y-1">
                {docs.map((d) => (
                  <li key={d.doc_id}>
                    <button
                      onClick={() => openDoc(d.doc_id)}
                      className={[
                        "w-full rounded px-3 py-2 text-left text-xs transition",
                        currentDocId === d.doc_id
                          ? "bg-brand-50 text-brand-800"
                          : "hover:bg-slate-100 text-slate-700",
                      ].join(" ")}
                    >
                      <div className="truncate font-medium">{d.filename}</div>
                      <div className="text-[10px] text-slate-500">
                        {d.doc_id} · {d.page_count}p
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {uploadResult && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-800">
              <div className="font-semibold">최근 업로드</div>
              <div className="mt-1">
                {uploadResult.filename} · {uploadResult.page_count}p
              </div>
              <div className="mt-2 text-[11px] font-mono">
                Sections {uploadResult.sections} · Tables {uploadResult.tables}{" "}
                · Rule hits {uploadResult.rule_hits}
              </div>
              <div className="mt-1 text-[11px] font-mono">
                Graph: {JSON.stringify(uploadResult.graph_stats)}
              </div>
            </div>
          )}
        </aside>

        <main className="min-w-0 space-y-4">
          {error && (
            <div className="rounded bg-red-50 p-3 text-xs text-red-700">
              {error}
            </div>
          )}

          {extraction ? (
            <>
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">
                      {extraction.filename}
                    </h2>
                    <p className="text-xs text-slate-500">
                      {extraction.page_count} pages ·{" "}
                      {extraction.sections.length} sections ·{" "}
                      {extraction.tables.length} tables ·{" "}
                      {extraction.references.length} references ·{" "}
                      {extraction.rule_hits.length} rule hits
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(extraction.appendices).map(([k, v]) => (
                      <span
                        key={k}
                        className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700"
                      >
                        Appendix {k} → p.{v}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <nav className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1 shadow-sm">
                {TABS.map((t) => (
                  <button
                    key={t.key}
                    onClick={() => setActiveTab(t.key)}
                    className={[
                      "flex-1 rounded-md px-3 py-2 text-sm font-medium transition",
                      activeTab === t.key
                        ? "bg-brand-600 text-white"
                        : "text-slate-700 hover:bg-slate-100",
                    ].join(" ")}
                  >
                    {t.label}
                  </button>
                ))}
              </nav>

              {activeTab === "extraction" && (
                <ExtractionTable data={extraction.extracted} />
              )}
              {activeTab === "references" && (
                <ReferencesView references={extraction.references} />
              )}
              {activeTab === "validation" && (
                <>
                  {loadingTab === "validation" ? (
                    <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 shadow-sm">
                      검증 중…
                    </div>
                  ) : validation ? (
                    <DependencyReport report={validation} />
                  ) : null}
                </>
              )}
              {activeTab === "similarity" && (
                <>
                  {loadingTab === "similarity" ? (
                    <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 shadow-sm">
                      과거 프로젝트 매칭 중… (임베딩 생성)
                    </div>
                  ) : similarity ? (
                    <SimilarProjects report={similarity} />
                  ) : null}
                </>
              )}
              {activeTab === "chat" && currentDocId && (
                <ChatPanel docId={currentDocId} />
              )}
              {activeTab === "review" && currentDocId && (
                <ReviewPanel
                  docId={currentDocId}
                  extraction={extraction}
                  validation={validation}
                />
              )}
            </>
          ) : (
            <div className="rounded-lg border-2 border-dashed border-slate-200 bg-white p-16 text-center text-sm text-slate-400">
              PDF를 업로드하거나 왼쪽 목록에서 문서를 선택하세요.
            </div>
          )}
        </main>
      </section>
    </div>
  );
}
