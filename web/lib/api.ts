// Tiny typed fetch layer. In dev, BASE is "" and Next proxies /api/* to FastAPI.
// In prod, NEXT_PUBLIC_API_BASE points straight at the deployed backend.
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}
async function post<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { method: "POST" });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

export type Firm = "A" | "B";

export interface FigureRow {
  figure: string;
  section: string;
  metric: string;
  value: string | null;
  limit: string | null;
  utilization: string | null;
  status: string | null;
  reconciled: string | null;
  error: string | null;
}

export interface FiguresResponse {
  firm: string;
  name: string;
  methods: Record<string, string>;
  graph_backend: string;
  summary: {
    reconciliation: { total: number; passed: number; failed: number; all_passed: boolean };
    firewall_passed: boolean;
    narrative_source: string;
  };
  figures: FigureRow[];
  narrative: string;
}

export interface FigureDetail {
  figure: string;
  metric: string;
  value: string | null;
  status: string | null;
  limit: string | null;
  utilization: string | null;
  graph_path: string | null;
  citation: { source_doc: string; page: number; chunk_id: string; passage_summary: string } | null;
  detail: Record<string, unknown> | null;
  error: string | null;
  reconciliation: { result?: string; checks?: Record<string, { got: string; expected: string; match: boolean; delta: string | null }> };
  produced_by_rule: Record<string, string>;
}

export interface AuditResponse {
  chain_intact: boolean | null;
  count?: number;
  events: { seq: number; ts: string; firm: string | null; event: string; trigger: string; payload: unknown; retention: string }[];
  note?: string;
}

export const api = {
  figures: (firm: Firm) => get<FiguresResponse>(`/api/figures?firm=${firm}`),
  figureDetail: (firm: Firm, id: string) => get<FigureDetail>(`/api/figures/${id}?firm=${firm}`),
  audit: () => get<AuditResponse>(`/api/audit`),
  config: (firm: Firm) => get<{ firm: string; yaml: string; methods: Record<string, string>; name: string }>(`/api/config/${firm}`),
  run: (firm: Firm) => post<Record<string, unknown>>(`/api/run?firm=${firm}`),
};
