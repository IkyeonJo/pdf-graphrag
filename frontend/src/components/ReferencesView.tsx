import type { Reference } from "../api/client";

const KIND_LABEL: Record<Reference["kind"], string> = {
  table: "Table",
  section: "Section",
  clause: "Clause",
  appendix: "Appendix",
  standard: "Standard",
};

const KIND_TONE: Record<Reference["kind"], string> = {
  table: "bg-indigo-100 text-indigo-800",
  section: "bg-sky-100 text-sky-800",
  clause: "bg-cyan-100 text-cyan-800",
  appendix: "bg-purple-100 text-purple-800",
  standard: "bg-emerald-100 text-emerald-800",
};

export function ReferencesView({ references }: { references: Reference[] }) {
  if (references.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-400 shadow-sm">
        탐지된 상호참조가 없습니다.
      </div>
    );
  }

  const grouped = references.reduce<Record<string, Reference[]>>((acc, r) => {
    const key = r.source_section ?? "(unknown)";
    (acc[key] ||= []).push(r);
    return acc;
  }, {});

  const sortedKeys = Object.keys(grouped).sort();

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-900">
          Jump Engine — 상호참조 {references.length}건
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          본문에서 다른 섹션/표/부록/표준을 참조하는 표현을 자동 감지한 결과입니다.
        </p>
      </div>
      <div className="divide-y divide-slate-100">
        {sortedKeys.map((sec) => (
          <div key={sec} className="px-4 py-3">
            <div className="mb-2 text-xs font-semibold text-slate-700">
              Section {sec}
            </div>
            <ul className="space-y-2">
              {grouped[sec].map((r, i) => (
                <li key={i} className="flex flex-wrap items-start gap-2 text-xs">
                  <span
                    className={`rounded px-2 py-0.5 font-medium ${KIND_TONE[r.kind]}`}
                  >
                    {KIND_LABEL[r.kind]}
                  </span>
                  <span className="font-mono text-slate-900">{r.target}</span>
                  {r.target_page !== null && (
                    <span className="text-slate-500">→ p.{r.target_page}</span>
                  )}
                  <span className="w-full pl-1 text-slate-500 italic">
                    “…{r.context}…”
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
