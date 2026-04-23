import { useEffect, useState } from "react";
import {
  api,
  type ExtractionResponse,
  type ReviewDecision,
  type ValidationReport,
} from "../api/client";

type Props = {
  docId: string;
  extraction: ExtractionResponse;
  validation: ValidationReport | null;
};

type EntityRow = {
  category: string;
  entity_key: string;
  label: string;
  page: number | null;
  severity?: string;
};

function keyOf(category: string, parts: (string | number | null)[]): string {
  return `${category}::${parts.filter((x) => x !== null && x !== "").join("|")}`;
}

function collectRows(
  extraction: ExtractionResponse,
  validation: ValidationReport | null,
): EntityRow[] {
  const rows: EntityRow[] = [];
  const ex = extraction.extracted;

  ex.items.forEach((it) => {
    rows.push({
      category: "items",
      entity_key: keyOf("items", [it.stock_code, it.description]),
      label: `${it.stock_code || "-"} · ${it.description}`,
      page: it.page,
    });
  });
  ex.materials.forEach((m) => {
    rows.push({
      category: "materials",
      entity_key: keyOf("materials", [m.grade]),
      label: `${m.grade}${m.standard ? ` [${m.standard}]` : ""}`,
      page: m.page,
    });
  });
  ex.standards.forEach((s) => {
    rows.push({
      category: "standards",
      entity_key: keyOf("standards", [s.code]),
      label: `${s.code} — ${s.title}`,
      page: s.page,
    });
  });
  ex.toxic_clauses.forEach((tc) => {
    rows.push({
      category: "toxic_clauses",
      entity_key: keyOf("toxic_clauses", [tc.text.slice(0, 80)]),
      label: tc.text,
      page: tc.page,
      severity: tc.severity,
    });
  });
  (validation?.issues ?? []).forEach((iss) => {
    rows.push({
      category: "validation",
      entity_key: keyOf("validation", [iss.rule_id]),
      label: `[${iss.rule_id}] ${iss.title}`,
      page: iss.evidence[0]?.page ?? null,
      severity: iss.severity,
    });
  });
  return rows;
}

const DECISION_TONE: Record<string, string> = {
  approved: "bg-emerald-100 text-emerald-800 border-emerald-300",
  rejected: "bg-red-100 text-red-800 border-red-300",
  pending: "bg-slate-100 text-slate-600 border-slate-200",
};

export function ReviewPanel({ docId, extraction, validation }: Props) {
  const [decisions, setDecisions] = useState<Map<string, ReviewDecision>>(
    new Map(),
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [category, setCategory] = useState<string>("toxic_clauses");

  useEffect(() => {
    void load();
  }, [docId]);

  async function load() {
    try {
      const st = await api.getReview(docId);
      const map = new Map<string, ReviewDecision>();
      st.decisions.forEach((d) => map.set(`${d.category}::${d.entity_key}`, d));
      setDecisions(map);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function decide(
    row: EntityRow,
    decision: "approved" | "rejected" | "pending",
  ) {
    setBusy(`${row.category}::${row.entity_key}`);
    try {
      await api.postDecision(docId, {
        category: row.category,
        entity_key: row.entity_key,
        decision,
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const rows = collectRows(extraction, validation);
  const categories = Array.from(new Set(rows.map((r) => r.category)));
  const filtered = rows.filter((r) => r.category === category);

  const summary = {
    total: rows.length,
    approved: Array.from(decisions.values()).filter(
      (d) => d.decision === "approved",
    ).length,
    rejected: Array.from(decisions.values()).filter(
      (d) => d.decision === "rejected",
    ).length,
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-900">
          Human-in-the-loop 검수
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          추출 결과 및 검증 이슈를 엔지니어가 승인/거부할 수 있습니다. 결정은
          `/data/indexes/reviews/{docId}.json`에 감사 로그와 함께 영속화됩니다.
        </p>
        <div className="mt-2 flex gap-4 text-xs text-slate-600">
          <span>
            전체 <span className="font-mono font-bold">{summary.total}</span>
          </span>
          <span className="text-emerald-700">
            승인 <span className="font-mono font-bold">{summary.approved}</span>
          </span>
          <span className="text-red-700">
            거부 <span className="font-mono font-bold">{summary.rejected}</span>
          </span>
        </div>
      </div>

      <nav className="flex flex-wrap gap-1 border-b border-slate-100 px-2 py-2">
        {categories.map((c) => {
          const count = rows.filter((r) => r.category === c).length;
          const active = c === category;
          return (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`rounded px-3 py-1.5 text-xs font-medium ${
                active
                  ? "bg-brand-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {c} <span className="ml-1 opacity-70">{count}</span>
            </button>
          );
        })}
      </nav>

      {error && (
        <div className="m-3 rounded bg-red-50 p-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <ul className="divide-y divide-slate-100">
        {filtered.map((r) => {
          const d = decisions.get(`${r.category}::${r.entity_key}`);
          const cur = d?.decision ?? "pending";
          const isBusy = busy === `${r.category}::${r.entity_key}`;
          return (
            <li key={r.entity_key} className="px-4 py-3">
              <div className="flex items-start gap-3">
                <div className="flex flex-1 flex-col">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    {r.severity && (
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                          r.severity === "High"
                            ? "bg-red-100 text-red-800"
                            : r.severity === "Medium"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {r.severity}
                      </span>
                    )}
                    <span className="text-slate-900">{r.label}</span>
                    {r.page !== null && (
                      <span className="text-xs text-slate-400">
                        p.{r.page}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex gap-1">
                  {(["approved", "rejected", "pending"] as const).map((act) => (
                    <button
                      key={act}
                      disabled={isBusy}
                      onClick={() => decide(r, act)}
                      className={`rounded border px-2 py-1 text-xs ${
                        cur === act
                          ? DECISION_TONE[act]
                          : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
                      }`}
                    >
                      {act === "approved" ? "승인" : act === "rejected" ? "거부" : "미결"}
                    </button>
                  ))}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
