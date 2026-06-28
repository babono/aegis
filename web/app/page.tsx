"use client";
import { useCallback, useEffect, useState } from "react";
import { api, Firm, FiguresResponse } from "@/lib/api";
import { StatusBadge, PassFail } from "./components/StatusBadge";
import { TracePanel } from "./components/TracePanel";
import { AuditPanel } from "./components/AuditPanel";
import { ConfigPanel } from "./components/ConfigPanel";

type Tab = "report" | "audit" | "config";

export default function Dashboard() {
  const [firm, setFirm] = useState<Firm>("A");
  const [tab, setTab] = useState<Tab>("report");
  const [data, setData] = useState<FiguresResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback((f: Firm) => {
    setLoading(true);
    setErr(null);
    api.figures(f)
      .then(setData)
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(firm); }, [firm, load]);

  const runPipeline = async () => {
    setRunning(true);
    try { await api.run(firm); load(firm); }
    catch (e) { setErr(String(e)); }
    finally { setRunning(false); }
  };

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Meridian Fixed Income — Compliance Report</h1>
          <p className="text-sm text-slate-400">
            Every figure is computed by a deterministic engine, traced through a knowledge
            graph to its source, and reconciled to the firm&apos;s answer key.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <FirmSwitch firm={firm} onChange={setFirm} />
          <button
            onClick={runPipeline}
            disabled={running}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold hover:bg-indigo-500 disabled:opacity-50"
          >
            {running ? "Running…" : "Run pipeline"}
          </button>
        </div>
      </header>

      {data && <SummaryBar data={data} />}

      <nav className="mb-4 mt-6 flex gap-1 border-b border-slate-800">
        {(["report", "audit", "config"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm capitalize ${
              tab === t ? "border-indigo-500 text-white" : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {t === "report" ? "Report" : t === "audit" ? "Audit log" : "Firm config"}
          </button>
        ))}
      </nav>

      {err && <p className="mb-4 rounded bg-rose-500/10 p-3 text-sm text-rose-300">{err} — is the API running on :8000?</p>}

      {tab === "report" && (
        <>
          {loading && <p className="text-slate-400">Computing figures…</p>}
          {data && <FiguresTable data={data} onSelect={setSelected} />}
          {data && (
            <div className="mt-6 rounded-lg bg-slate-900 p-4 ring-1 ring-slate-800">
              <p className="mb-1 text-xs uppercase text-slate-500">LLM narrative (commentary only — firewall-verified)</p>
              <p className="text-sm text-slate-300">{data.narrative}</p>
            </div>
          )}
        </>
      )}
      {tab === "audit" && <AuditPanel />}
      {tab === "config" && <ConfigPanel />}

      {selected && <TracePanel firm={firm} figureId={selected} onClose={() => setSelected(null)} />}
    </main>
  );
}

function FirmSwitch({ firm, onChange }: { firm: Firm; onChange: (f: Firm) => void }) {
  return (
    <div className="flex overflow-hidden rounded-lg ring-1 ring-slate-700">
      {(["A", "B"] as Firm[]).map((f) => (
        <button
          key={f}
          onClick={() => onChange(f)}
          className={`px-4 py-2 text-sm font-medium ${firm === f ? "bg-slate-700 text-white" : "bg-slate-900 text-slate-400 hover:bg-slate-800"}`}
        >
          Firm {f}
        </button>
      ))}
    </div>
  );
}

function SummaryBar({ data }: { data: FiguresResponse }) {
  const r = data.summary.reconciliation;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Chip label="Configuration" value={data.name.replace(/^Firm [AB] — /, "")} />
      <Chip label="Reconciliation" value={`${r.passed}/${r.total} match`} good={r.all_passed} />
      <Chip label="No-LLM-numbers firewall" value={data.summary.firewall_passed ? "passed" : "failed"} good={data.summary.firewall_passed} />
      <Chip label="Graph backend" value={data.graph_backend} />
    </div>
  );
}

function Chip({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="rounded-lg bg-slate-900 p-3 ring-1 ring-slate-800">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-0.5 text-sm font-semibold ${good === undefined ? "" : good ? "text-emerald-400" : "text-rose-400"}`}>{value}</p>
    </div>
  );
}

function FiguresTable({ data, onSelect }: { data: FiguresResponse; onSelect: (id: string) => void }) {
  let section = "";
  return (
    <table className="w-full overflow-hidden rounded-lg text-sm ring-1 ring-slate-800">
      <thead className="bg-slate-900 text-left text-slate-400">
        <tr>
          <th className="px-4 py-2">Metric</th>
          <th className="px-4 py-2">Value</th>
          <th className="px-4 py-2">Limit</th>
          <th className="px-4 py-2">Utilization</th>
          <th className="px-4 py-2">Status</th>
          <th className="px-4 py-2">vs key</th>
          <th className="px-4 py-2"></th>
        </tr>
      </thead>
      <tbody>
        {data.figures.map((f) => {
          const header = f.section !== section ? ((section = f.section), f.section) : null;
          return (
            <FragmentRow key={f.figure} header={header}>
              <tr
                onClick={() => onSelect(f.figure)}
                className="cursor-pointer border-t border-slate-800 hover:bg-slate-900"
              >
                <td className="px-4 py-2">{f.metric}</td>
                <td className="px-4 py-2 font-medium">{f.value ?? "—"}</td>
                <td className="px-4 py-2 text-slate-400">{f.limit ?? "—"}</td>
                <td className="px-4 py-2 text-slate-400">{f.utilization ?? "—"}</td>
                <td className="px-4 py-2"><StatusBadge status={f.status} /></td>
                <td className="px-4 py-2"><PassFail result={f.reconciled} /></td>
                <td className="px-4 py-2 text-right text-xs text-indigo-400">trace →</td>
              </tr>
            </FragmentRow>
          );
        })}
      </tbody>
    </table>
  );
}

function FragmentRow({ header, children }: { header: string | null; children: React.ReactNode }) {
  return (
    <>
      {header && (
        <tr className="bg-slate-950/60">
          <td colSpan={7} className="px-4 pt-3 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{header}</td>
        </tr>
      )}
      {children}
    </>
  );
}
