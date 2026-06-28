"use client";
import { useCallback, useEffect, useState } from "react";
import { api, onWaking, Firm, FiguresResponse } from "@/lib/api";
import { StatusBadge, PassFail } from "./components/StatusBadge";
import { TracePanel } from "./components/TracePanel";
import { AuditPanel } from "./components/AuditPanel";
import { ConfigPanel } from "./components/ConfigPanel";
import { HowItWorks } from "./components/HowItWorks";
import { Logo } from "./components/Logo";

type Tab = "report" | "audit" | "config";

export default function Dashboard() {
  const [firm, setFirm] = useState<Firm>("A");
  const [tab, setTab] = useState<Tab>("report");
  const [data, setData] = useState<FiguresResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [waking, setWaking] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => { onWaking(setWaking); }, []);

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
    <div className="min-h-screen">
      {/* Brand bar */}
      <div className="border-b border-line bg-bg">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-3">
          <Logo size={34} />
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-black tracking-tight text-ink-0">Aegis</span>
            <span className="hidden text-xs text-ink-3 sm:inline">
              Auditable Engine for Graph-Integrated Source-tracking
            </span>
          </div>
          <span className="ml-auto rounded bg-primary-soft px-2 py-1 text-xs font-semibold text-road-text">
            InterOpera
          </span>
        </div>
      </div>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-ink-0">Meridian Fixed Income — Compliance Report</h1>
            <p className="text-sm text-ink-2">
              Every figure is computed by a deterministic engine, traced through a knowledge
              graph to its source, and reconciled to the firm&apos;s answer key.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <FirmSwitch firm={firm} onChange={setFirm} />
            <button
              onClick={runPipeline}
              disabled={running}
              className="rounded bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-hover disabled:opacity-50"
            >
              {running ? "Running…" : "Run pipeline"}
            </button>
          </div>
        </header>

        {waking && (
          <div className="mb-4 rounded border border-warn-line bg-warn-bg px-4 py-3 text-sm text-warn-text">
            ⏳ Waking the backend up… the free-tier server sleeps when idle, so the first
            load can take ~30–60 seconds. Hang tight — it&apos;ll load automatically.
          </div>
        )}

        {data && <SummaryBar data={data} />}

        <HowItWorks />

        <nav className="mb-4 mt-6 flex gap-1 border-b border-line">
          {(["report", "audit", "config"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize ${
                tab === t ? "border-primary text-ink-0" : "border-transparent text-ink-3 hover:text-ink-1"
              }`}
            >
              {t === "report" ? "Report" : t === "audit" ? "Audit log" : "Firm config"}
            </button>
          ))}
        </nav>

        {err && !waking && (
          <p className="mb-4 rounded border border-danger-line bg-danger-bg p-3 text-sm text-danger-text">
            Couldn&apos;t reach the API ({err}). The backend may still be waking up — try again in a moment.
          </p>
        )}

        {tab === "report" && (
          <>
            {loading && <p className="text-ink-3">Computing figures…</p>}
            {data && <FiguresTable data={data} onSelect={setSelected} />}
            {data && (
              <div className="mt-6 rounded-lg border border-line bg-bg p-4">
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">
                  LLM narrative (commentary only — firewall-verified)
                </p>
                <p className="text-sm text-ink-1">{data.narrative}</p>
              </div>
            )}
          </>
        )}
        {tab === "audit" && <AuditPanel />}
        {tab === "config" && <ConfigPanel />}

        {selected && <TracePanel firm={firm} figureId={selected} onClose={() => setSelected(null)} />}

        <footer className="mt-12 border-t border-line pt-6 text-xs text-ink-3">
          <p>
            <span className="font-semibold text-ink-1">Aegis</span> — figures are computed by a
            deterministic engine traversing a knowledge graph, traced to their source passage, and
            reconciled to each firm&apos;s answer key. The language model writes narrative only,
            behind a firewall.
          </p>
          <p className="mt-2">
            <a href="https://github.com/babono/aegis" target="_blank" rel="noreferrer"
               className="font-semibold text-primary hover:text-primary-hover">
              Source on GitHub →
            </a>
          </p>
        </footer>
      </main>
    </div>
  );
}

function FirmSwitch({ firm, onChange }: { firm: Firm; onChange: (f: Firm) => void }) {
  return (
    <div className="flex overflow-hidden rounded border border-line-dark">
      {(["A", "B"] as Firm[]).map((f) => (
        <button
          key={f}
          onClick={() => onChange(f)}
          className={`px-4 py-2 text-sm font-semibold ${firm === f ? "bg-primary text-white" : "bg-bg text-ink-2 hover:bg-bg-soft"}`}
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
    <div className="rounded-lg border border-line bg-bg p-3">
      <p className="text-xs text-ink-3">{label}</p>
      <p className={`mt-0.5 text-sm font-bold ${good === undefined ? "text-ink-1" : good ? "text-ok-text" : "text-danger-text"}`}>{value}</p>
    </div>
  );
}

function FiguresTable({ data, onSelect }: { data: FiguresResponse; onSelect: (id: string) => void }) {
  let section = "";
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-bg">
      <table className="w-full text-sm">
        <thead className="bg-bg-soft text-left text-ink-2">
          <tr>
            <th className="px-4 py-2 font-semibold" title="The rule being checked">Metric</th>
            <th className="px-4 py-2 font-semibold" title="What the fund actually is">Value</th>
            <th className="px-4 py-2 font-semibold" title="What the rule allows">Limit</th>
            <th className="px-4 py-2 font-semibold" title="How much of the limit is used (Firm B reports basis points: 6000 bps = 60%)">Utilization</th>
            <th className="px-4 py-2 font-semibold" title="OK = within limit · AT LIMIT = exactly at it · BREACH = outside it">Status</th>
            <th className="px-4 py-2 font-semibold" title="Matches the official answer key">vs key</th>
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
                  className="cursor-pointer border-t border-line hover:bg-primary-soft/40"
                >
                  <td className="px-4 py-2 text-ink-1">{f.metric}</td>
                  <td className="px-4 py-2 font-semibold text-ink-0">{f.value ?? "—"}</td>
                  <td className="px-4 py-2 text-ink-2">{f.limit ?? "—"}</td>
                  <td className="px-4 py-2 text-ink-2"><Util util={f.utilization} /></td>
                  <td className="px-4 py-2"><StatusBadge status={f.status} /></td>
                  <td className="px-4 py-2"><PassFail result={f.reconciled} /></td>
                  <td className="px-4 py-2 text-right text-xs font-medium text-primary">trace →</td>
                </tr>
              </FragmentRow>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Firm B reports utilization in truncated basis points (e.g. "5833 bps"). Show a
// muted percentage hint so it's readable at a glance (5833 bps = 58.3%).
function Util({ util }: { util: string | null }) {
  if (!util) return <>—</>;
  const m = util.match(/^(\d+)\s*bps$/);
  if (!m) return <>{util}</>;
  const pct = (parseInt(m[1], 10) / 100).toFixed(1);
  return (
    <span>
      {util} <span className="text-ink-4">({pct}%)</span>
    </span>
  );
}

function FragmentRow({ header, children }: { header: string | null; children: React.ReactNode }) {
  return (
    <>
      {header && (
        <tr className="bg-bg-soft/60">
          <td colSpan={7} className="px-4 pt-3 pb-1 text-xs font-bold uppercase tracking-wide text-ink-3">{header}</td>
        </tr>
      )}
      {children}
    </>
  );
}
