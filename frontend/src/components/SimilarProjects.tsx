import type { SimilarityReport } from "../api/client";

function scoreTone(score: number): string {
  if (score >= 0.5) return "bg-emerald-100 text-emerald-800 border-emerald-300";
  if (score >= 0.35) return "bg-amber-100 text-amber-800 border-amber-300";
  return "bg-slate-100 text-slate-700 border-slate-300";
}

function outcomeTone(outcome: string): string {
  if (outcome.includes("수주 성공")) return "text-emerald-700";
  if (outcome.includes("포기")) return "text-red-700";
  return "text-slate-600";
}

export function SimilarProjects({ report }: { report: SimilarityReport }) {
  if (report.matches.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-400 shadow-sm">
        과거 프로젝트 데이터가 없습니다.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-900">
          유사 과거 프로젝트 — 상위 {report.matches.length}건
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          임베딩(의미) 60% + 그래프 overlap(공통 표준/재질) 40% 하이브리드 스코어
        </p>
      </div>
      <ul className="divide-y divide-slate-100">
        {report.matches.map((m, idx) => (
          <li key={m.id} className="px-4 py-4">
            <div className="flex items-start gap-3">
              <span
                className={`rounded-full border px-3 py-1 text-sm font-bold ${scoreTone(m.score)}`}
              >
                {(m.score * 100).toFixed(0)}%
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="text-xs text-slate-400">#{idx + 1}</span>
                  <h4 className="text-sm font-semibold text-slate-900">
                    {m.title}
                  </h4>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                  <span>{m.client}</span>
                  <span>•</span>
                  <span>{m.year}</span>
                  <span>•</span>
                  <span>{m.scale}</span>
                  <span>•</span>
                  <span className={outcomeTone(m.outcome)}>{m.outcome}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-3 text-[11px] font-mono text-slate-500">
                  <span>cosine={m.cosine.toFixed(3)}</span>
                  <span>jaccard={m.jaccard.toFixed(3)}</span>
                </div>

                {m.shared_standards.length > 0 && (
                  <div className="mt-2">
                    <span className="text-xs text-slate-500">
                      공통 표준 ({m.shared_standards.length}):
                    </span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {m.shared_standards.map((s) => (
                        <span
                          key={s}
                          className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-mono text-emerald-800"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {m.shared_materials.length > 0 && (
                  <div className="mt-2">
                    <span className="text-xs text-slate-500">
                      공통 재질 ({m.shared_materials.length}):
                    </span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {m.shared_materials.map((s) => (
                        <span
                          key={s}
                          className="rounded bg-indigo-50 px-2 py-0.5 text-xs font-mono text-indigo-800"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
