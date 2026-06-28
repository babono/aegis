"use client";
import { useEffect, useState } from "react";
import { api, Firm, FigureDetail } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

// The replay viewer: figure -> graph path -> source, plus delta vs answer key
// and which config rule produced it.
export function TracePanel({ firm, figureId, onClose }: { firm: Firm; figureId: string; onClose: () => void }) {
  const [d, setD] = useState<FigureDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setD(null);
    api.figureDetail(firm, figureId).then(setD).catch((e) => setErr(String(e)));
  }, [firm, figureId]);

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50" onClick={onClose}>
      <div
        className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-800 bg-slate-900 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {err && <p className="text-rose-400">{err}</p>}
        {!d && !err && <p className="text-slate-400">Loading trace…</p>}
        {d && (
          <div className="space-y-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">{d.figure}</p>
                <h2 className="text-lg font-semibold">{d.metric}</h2>
              </div>
              <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-800">✕</button>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <Stat label="Value" value={d.value} big />
              <Stat label="Limit" value={d.limit} />
              <div>
                <p className="text-xs text-slate-500">Status</p>
                <div className="mt-1"><StatusBadge status={d.status} /></div>
              </div>
            </div>

            {/* Reconciliation vs answer key */}
            <Section title="Reconciliation vs answer key">
              {d.reconciliation?.checks ? (
                <table className="w-full text-sm">
                  <tbody>
                    {Object.entries(d.reconciliation.checks).map(([k, c]) => (
                      <tr key={k} className="border-t border-slate-800">
                        <td className="py-1 capitalize text-slate-400">{k}</td>
                        <td className="py-1">{c.got}</td>
                        <td className="py-1 text-slate-500">exp {c.expected}</td>
                        <td className="py-1 text-right">{c.match ? <span className="text-emerald-400">✓</span> : <span className="text-rose-400">✗ Δ{c.delta ?? ""}</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-slate-400">{d.reconciliation?.result ?? "—"}</p>
              )}
            </Section>

            {/* Graph path = constraint 2 traceability */}
            <Section title="Graph path (figure → graph → source)">
              <code className="block whitespace-pre-wrap break-words rounded bg-slate-950 p-3 text-xs text-cyan-300 ring-1 ring-slate-800">
                {d.graph_path}
              </code>
            </Section>

            {/* Source citation */}
            <Section title="Source citation">
              {d.citation ? (
                <div className="rounded bg-slate-950 p-3 text-sm ring-1 ring-slate-800">
                  <p className="font-medium">{d.citation.source_doc} · p.{d.citation.page}</p>
                  <p className="text-slate-400">{d.citation.passage_summary}</p>
                  <p className="mt-1 text-xs text-slate-600">chunk {d.citation.chunk_id}</p>
                </div>
              ) : <p className="text-slate-500">—</p>}
            </Section>

            {/* Which config rule produced this figure */}
            <Section title="Produced by config rule">
              <div className="flex flex-wrap gap-2">
                {Object.entries(d.produced_by_rule).map(([k, v]) => (
                  <span key={k} className="rounded bg-indigo-500/15 px-2 py-1 text-xs text-indigo-300 ring-1 ring-indigo-500/30">
                    {k} = {v}
                  </span>
                ))}
              </div>
            </Section>

            <p className="text-xs text-slate-600">
              This figure was computed by the deterministic engine traversing the graph. The
              language model is not in this path.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, big }: { label: string; value: string | null; big?: boolean }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-1 ${big ? "text-2xl font-semibold" : "text-sm"}`}>{value ?? "—"}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {children}
    </div>
  );
}
