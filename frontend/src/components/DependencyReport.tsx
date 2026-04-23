import type { ValidationReport } from "../api/client";

const SEVERITY_TONE: Record<string, string> = {
  High: "border-red-400 bg-red-50",
  Medium: "border-amber-400 bg-amber-50",
  Low: "border-slate-300 bg-slate-50",
};

const SEVERITY_BADGE: Record<string, string> = {
  High: "bg-red-100 text-red-800",
  Medium: "bg-amber-100 text-amber-800",
  Low: "bg-slate-200 text-slate-700",
};

export function DependencyReport({ report }: { report: ValidationReport }) {
  const { issues, passed } = report;

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-900">
          의존성 교차 검증 — 이슈 {issues.length}건, 통과 {passed.length}건
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          코리아스틸 사내 표준(한글 JSON) ↔ 영문 사양서 추출 결과를 Cypher/룰로
          교차 검증했습니다. 독소조항과 기술 리스크를 자동으로 가려냅니다.
        </p>
      </div>

      {issues.length === 0 ? (
        <div className="p-8 text-center text-sm text-emerald-700">
          ✓ 모든 검증 규칙 통과
        </div>
      ) : (
        <ul className="divide-y divide-slate-100">
          {issues.map((issue) => (
            <li
              key={issue.rule_id}
              className={`border-l-4 px-4 py-3 ${SEVERITY_TONE[issue.severity] ?? ""}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium ${SEVERITY_BADGE[issue.severity]}`}
                >
                  {issue.severity}
                </span>
                <span className="rounded bg-slate-900 px-2 py-0.5 text-xs font-mono text-white">
                  {issue.rule_id}
                </span>
                <span className="text-sm font-semibold text-slate-900">
                  {issue.title}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-700">{issue.detail}</p>
              {issue.evidence.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs text-slate-600">
                  {issue.evidence.map((e, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="mt-0.5 text-slate-400">•</span>
                      <span>
                        {e.description}
                        {e.page !== null && (
                          <span className="ml-1 text-slate-400">
                            (p.{e.page})
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}

      {passed.length > 0 && (
        <div className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
          통과한 규칙:{" "}
          <span className="font-mono text-emerald-700">
            {passed.join(", ")}
          </span>
        </div>
      )}
    </div>
  );
}
