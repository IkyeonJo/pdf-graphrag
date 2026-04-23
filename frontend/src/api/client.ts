const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText} ${text}`);
  }
  return res.json() as Promise<T>;
}

export type HealthResponse = {
  status: string;
  company: string;
  llm_backend: string;
  llm_model: string;
};

export type UploadResponse = {
  doc_id: string;
  filename: string;
  page_count: number;
  sections: number;
  tables: number;
  rule_hits: number;
  graph_stats: Record<string, number>;
};

export type DocumentListItem = {
  doc_id: string;
  filename: string;
  page_count: number;
};

export type SectionOut = {
  number: string;
  title: string;
  page_start: number;
  page_end: number | null;
  depth: number;
};

export type ExtractedDocument = {
  items: { stock_code: string; description: string; page: number | null }[];
  materials: { grade: string; standard: string; page: number | null }[];
  dimensions: { subject: string; value: string; unit: string; page: number | null }[];
  environmental: { type: string; value: string; unit: string; page: number | null }[];
  electrical: { type: string; value: string; unit: string; page: number | null }[];
  standards: { code: string; title: string; page: number | null }[];
  tests: { category: string; criterion: string; reference: string; page: number | null }[];
  marking: { description: string; page: number | null }[];
  packaging: { description: string; page: number | null }[];
  storage: { description: string; page: number | null }[];
  lifespan: { description: string; page: number | null }[];
  samples: { description: string; page: number | null }[];
  training: { description: string; page: number | null }[];
  delivery: { description: string; page: number | null }[];
  toxic_clauses: { text: string; severity: string; reason: string; page: number | null }[];
};

export type Reference = {
  kind: "table" | "section" | "clause" | "appendix" | "standard";
  target: string;
  source_page: number;
  source_section: string | null;
  target_page: number | null;
  context: string;
};

export type ExtractionResponse = {
  doc_id: string;
  filename: string;
  page_count: number;
  sections: SectionOut[];
  appendices: Record<string, number>;
  tables: { page: number; index: number; headers: string[]; rows: string[][] }[];
  rule_hits: { kind: string; value: string; page: number }[];
  references: Reference[];
  extracted: ExtractedDocument;
};

export type ValidationIssue = {
  rule_id: string;
  severity: "High" | "Medium" | "Low";
  title: string;
  detail: string;
  evidence: { description: string; page: number | null }[];
};

export type ValidationReport = {
  doc_id: string;
  issues: ValidationIssue[];
  passed: string[];
};

export type MatchedProject = {
  id: string;
  title: string;
  client: string;
  year: number;
  outcome: string;
  scale: string;
  score: number;
  cosine: number;
  jaccard: number;
  shared_standards: string[];
  shared_materials: string[];
};

export type SimilarityReport = {
  doc_id: string;
  matches: MatchedProject[];
  query_summary: string;
};

export type ChatCitation = {
  description: string;
  category: string;
  page: number | null;
};

export type ChatAnswer = {
  answer: string;
  citations: ChatCitation[];
  used_graph_facts: number;
};

export type ReviewDecision = {
  category: string;
  entity_key: string;
  decision: "approved" | "rejected" | "pending";
  note: string;
  decided_at: string;
  decided_by: string;
};

export type ReviewState = {
  doc_id: string;
  decisions: ReviewDecision[];
};

export const api = {
  health: () => request<HealthResponse>("/health"),
  llmPing: () => request<{ reply: string }>("/llm/ping"),
  listDocuments: () => request<DocumentListItem[]>("/documents"),
  getExtraction: (docId: string) =>
    request<ExtractionResponse>(`/extraction/${docId}`),
  getValidation: (docId: string) =>
    request<ValidationReport>(`/validation/${docId}`),
  getSimilarity: (docId: string, topK = 4) =>
    request<SimilarityReport>(`/similarity/${docId}?top_k=${topK}`),
  chat: (docId: string, question: string) =>
    request<ChatAnswer>(`/chat/${docId}`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  getReview: (docId: string) => request<ReviewState>(`/review/${docId}`),
  postDecision: (
    docId: string,
    body: {
      category: string;
      entity_key: string;
      decision: "approved" | "rejected" | "pending";
      note?: string;
    },
  ) =>
    request<ReviewState>(`/review/${docId}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  upload: async (file: File): Promise<UploadResponse> => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResponse>("/upload", { method: "POST", body: form });
  },
};
