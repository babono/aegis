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
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-0/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-xl overflow-y-auto border-l border-line bg-bg p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {err && <p className="text-danger-text">{err}</p>}
        {!d && !err && <p className="text-ink-3">Loading trace…</p>}
        {d && (
          <div className="space-y-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-3">{d.figure}</p>
                <h2 className="text-lg font-bold text-ink-0">{d.metric}</h2>
              </div>
              <button onClick={onClose} className="rounded p-1 text-ink-3 hover:bg-bg-soft">✕</button>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <Stat label="Value" value={d.value} big />
              <Stat label="Limit" value={d.limit} />
              <div>
                <p className="text-xs text-ink-3">Status</p>
                <div className="mt-1"><StatusBadge status={d.status} /></div>
              </div>
            </div>

            {/* Reconciliation vs answer key */}
            <Section title="Reconciliation vs answer key">
              {d.reconciliation?.checks ? (
                <table className="w-full text-sm">
                  <tbody>
                    {Object.entries(d.reconciliation.checks).map(([k, c]) => (
                      <tr key={k} className="border-t border-line">
                        <td className="py-1 capitalize text-ink-2">{k}</td>
                        <td className="py-1 text-ink-1">{c.got}</td>
                        <td className="py-1 text-ink-3">exp {c.expected}</td>
                        <td className="py-1 text-right">{c.match ? <span className="text-ok-text">✓</span> : <span className="text-danger-text">✗ Δ{c.delta ?? ""}</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-ink-2">{d.reconciliation?.result ?? "—"}</p>
              )}
            </Section>

            {/* Graph path = constraint 2 traceability */}
            <Section title="Graph path (figure → graph → source)">
              <code className="block whitespace-pre-wrap break-words rounded border border-line bg-bg-soft p-3 text-xs text-ink-1">
                {d.graph_path}
              </code>
            </Section>

            {/* Source citation */}
            <Section title="Source citation">
              {d.citation ? (
                <div className="rounded border border-line bg-bg-soft p-3 text-sm">
                  <p className="font-semibold text-ink-0">{d.citation.source_doc} · p.{d.citation.page}</p>
                  <p className="text-ink-2">{d.citation.passage_summary}</p>
                  <p className="mt-1 text-xs text-ink-4">chunk {d.citation.chunk_id}</p>
                </div>
              ) : <p className="text-ink-3">—</p>}
            </Section>

            {/* Which config rule produced this figure */}
            <Section title="Produced by config rule">
              <div className="flex flex-wrap gap-2">
                {Object.entries(d.produced_by_rule).map(([k, v]) => (
                  <span key={k} className="rounded border border-road-line bg-road-bg px-2 py-1 text-xs font-medium text-road-text">
                    {k} = {v}
                  </span>
                ))}
              </div>
            </Section>

            <p className="text-xs text-ink-3">
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
      <p className="text-xs text-ink-3">{label}</p>
      <p className={`mt-1 ${big ? "text-2xl font-bold text-ink-0" : "text-sm text-ink-1"}`}>{value ?? "—"}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-3">{title}</h3>
      {children}
    </div>
  );
}
