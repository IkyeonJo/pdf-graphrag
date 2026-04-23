import { useState } from "react";
import { api, type ChatAnswer } from "../api/client";

type Turn = {
  question: string;
  answer: ChatAnswer | null;
  error?: string;
};

const CATEGORY_TONE: Record<string, string> = {
  items: "bg-indigo-50 text-indigo-800",
  materials: "bg-violet-50 text-violet-800",
  standards: "bg-emerald-50 text-emerald-800",
  environmental: "bg-sky-50 text-sky-800",
  electrical: "bg-amber-50 text-amber-800",
  tests: "bg-pink-50 text-pink-800",
  toxic_clauses: "bg-red-50 text-red-800",
  references: "bg-slate-100 text-slate-700",
  sections: "bg-slate-50 text-slate-600",
};

const PRESET_QUESTIONS = [
  "이 입찰에서 가장 불리한 독소조항 3개를 나열해줘",
  "Saliferous 환경에서 이 볼트 사양이 안전한가?",
  "본문에서 참조하지만 References 섹션에 누락된 표준이 있나?",
  "Table 1.1의 품목 중 M16 볼트 목록과 강도 요구사항은?",
];

export function ChatPanel({ docId }: { docId: string }) {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setBusy(true);
    const placeholder: Turn = { question, answer: null };
    setTurns((ts) => [...ts, placeholder]);
    setInput("");
    try {
      const answer = await api.chat(docId, question);
      setTurns((ts) =>
        ts.map((t, i) => (i === ts.length - 1 ? { ...t, answer } : t)),
      );
    } catch (e) {
      setTurns((ts) =>
        ts.map((t, i) =>
          i === ts.length - 1
            ? { ...t, error: e instanceof Error ? e.message : String(e) }
            : t,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-320px)] min-h-[420px] flex-col rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-900">
          GraphRAG 챗봇
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          추출 데이터 + Neo4j 그래프 사실(MENTIONS / REFERS_TO / HAS_RISK
          엣지)을 컨텍스트로 답변합니다. 근거 페이지 자동 인용.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {turns.length === 0 ? (
          <div className="space-y-3">
            <p className="text-xs text-slate-400">예시 질문을 클릭해보세요:</p>
            <div className="flex flex-col gap-2">
              {PRESET_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => ask(q)}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-left text-sm text-slate-700 hover:border-brand-400 hover:bg-brand-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {turns.map((t, i) => (
              <div key={i} className="space-y-3">
                <div className="ml-auto max-w-[85%] rounded-lg bg-brand-600 px-4 py-2 text-sm text-white">
                  {t.question}
                </div>
                {t.answer ? (
                  <div className="max-w-[90%] rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-900">
                    <div className="whitespace-pre-wrap">{t.answer.answer}</div>
                    {t.answer.citations.length > 0 && (
                      <div className="mt-3 border-t border-slate-200 pt-2">
                        <div className="mb-1 text-[11px] font-semibold text-slate-500">
                          근거 ({t.answer.citations.length})
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {t.answer.citations.map((c, j) => (
                            <span
                              key={j}
                              className={`rounded px-2 py-0.5 text-[11px] ${
                                CATEGORY_TONE[c.category] ?? "bg-slate-100 text-slate-700"
                              }`}
                            >
                              {c.category}
                              {c.page !== null ? ` · p.${c.page}` : ""}
                              <span className="ml-1 opacity-70">
                                {c.description}
                              </span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="mt-2 text-[10px] text-slate-400">
                      graph facts used: {t.answer.used_graph_facts}
                    </div>
                  </div>
                ) : t.error ? (
                  <div className="max-w-[90%] rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
                    {t.error}
                  </div>
                ) : (
                  <div className="max-w-[90%] rounded-lg bg-slate-50 px-4 py-2 text-sm text-slate-500">
                    그래프 질의 중…
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
        className="border-t border-slate-200 p-3"
      >
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="이 사양서에 대해 물어보세요…"
            disabled={busy}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:bg-slate-100"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:bg-slate-300"
          >
            {busy ? "…" : "전송"}
          </button>
        </div>
      </form>
    </div>
  );
}
