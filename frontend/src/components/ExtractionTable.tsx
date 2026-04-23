import { useState } from "react";
import type { ExtractedDocument } from "../api/client";

const CATEGORY_META: Array<{
  key: keyof ExtractedDocument;
  label: string;
  columns: { field: string; header: string }[];
}> = [
  {
    key: "items",
    label: "품목 (Items)",
    columns: [
      { field: "stock_code", header: "Stock Code" },
      { field: "description", header: "Description" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "materials",
    label: "재질 (Materials)",
    columns: [
      { field: "grade", header: "Grade" },
      { field: "standard", header: "Standard" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "dimensions",
    label: "치수 (Dimensions)",
    columns: [
      { field: "subject", header: "Subject" },
      { field: "value", header: "Value" },
      { field: "unit", header: "Unit" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "environmental",
    label: "환경 (Environmental)",
    columns: [
      { field: "type", header: "Type" },
      { field: "value", header: "Value" },
      { field: "unit", header: "Unit" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "electrical",
    label: "전기 (Electrical)",
    columns: [
      { field: "type", header: "Type" },
      { field: "value", header: "Value" },
      { field: "unit", header: "Unit" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "standards",
    label: "표준 (Standards)",
    columns: [
      { field: "code", header: "Code" },
      { field: "title", header: "Title" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "tests",
    label: "시험 (Tests)",
    columns: [
      { field: "category", header: "Category" },
      { field: "criterion", header: "Criterion" },
      { field: "reference", header: "Reference" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "marking",
    label: "마킹 (Marking)",
    columns: [
      { field: "description", header: "Description" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "packaging",
    label: "포장 (Packaging)",
    columns: [
      { field: "description", header: "Description" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "storage",
    label: "보관 (Storage)",
    columns: [
      { field: "description", header: "Description" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "lifespan",
    label: "수명 (Lifespan)",
    columns: [
      { field: "description", header: "Description" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "samples",
    label: "샘플 (Samples)",
    columns: [
      { field: "description", header: "Description" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "training",
    label: "교육 (Training)",
    columns: [
      { field: "description", header: "Description" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "delivery",
    label: "납품 (Delivery)",
    columns: [
      { field: "description", header: "Description" },
      { field: "page", header: "Page" },
    ],
  },
  {
    key: "toxic_clauses",
    label: "독소조항 (Toxic)",
    columns: [
      { field: "severity", header: "Severity" },
      { field: "text", header: "Clause" },
      { field: "reason", header: "Reason" },
      { field: "page", header: "Page" },
    ],
  },
];

function Badge({ severity }: { severity: string }) {
  const tone =
    severity === "High"
      ? "bg-red-100 text-red-800"
      : severity === "Medium"
        ? "bg-amber-100 text-amber-800"
        : "bg-slate-100 text-slate-700";
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${tone}`}>
      {severity}
    </span>
  );
}

export function ExtractionTable({ data }: { data: ExtractedDocument }) {
  const [active, setActive] = useState<keyof ExtractedDocument>("items");
  const meta = CATEGORY_META.find((m) => m.key === active)!;
  const rows = (data[active] ?? []) as Record<string, unknown>[];

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <nav className="flex flex-wrap gap-1 border-b border-slate-200 px-2 py-2">
        {CATEGORY_META.map((m) => {
          const count = (data[m.key] as unknown[] | undefined)?.length ?? 0;
          const isActive = m.key === active;
          return (
            <button
              key={m.key}
              onClick={() => setActive(m.key)}
              className={[
                "rounded px-3 py-1.5 text-xs font-medium transition",
                isActive
                  ? "bg-brand-600 text-white"
                  : "text-slate-600 hover:bg-slate-100",
              ].join(" ")}
            >
              {m.label}
              <span
                className={[
                  "ml-2 rounded-full px-1.5 py-0.5 text-[10px]",
                  isActive ? "bg-white/20" : "bg-slate-200 text-slate-600",
                ].join(" ")}
              >
                {count}
              </span>
            </button>
          );
        })}
      </nav>

      <div className="overflow-x-auto">
        {rows.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">
            이 카테고리에서 추출된 엔티티가 없습니다.
          </div>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                {meta.columns.map((c) => (
                  <th
                    key={c.field}
                    className="px-4 py-2 text-left font-medium text-slate-600"
                  >
                    {c.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row, idx) => (
                <tr key={idx} className="hover:bg-slate-50">
                  {meta.columns.map((c) => {
                    const v = row[c.field];
                    if (c.field === "severity" && typeof v === "string") {
                      return (
                        <td key={c.field} className="px-4 py-2">
                          <Badge severity={v} />
                        </td>
                      );
                    }
                    return (
                      <td
                        key={c.field}
                        className="px-4 py-2 align-top text-slate-800"
                      >
                        {v === null || v === undefined || v === ""
                          ? "–"
                          : String(v)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
