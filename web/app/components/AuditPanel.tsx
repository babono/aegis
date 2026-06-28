"use client";
import { useEffect, useState } from "react";
import { api, AuditResponse } from "@/lib/api";

export function AuditPanel() {
  const [data, setData] = useState<AuditResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.audit().then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="text-rose-400">{err}</p>;
  if (!data) return <p className="text-slate-400">Loading audit log…</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-400">Append-only · hash-chained · UPDATE/DELETE blocked</span>
        {data.chain_intact === null ? (
          <span className="rounded-full bg-slate-700/40 px-3 py-1 text-xs text-slate-300">no log yet — run the pipeline</span>
        ) : (
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${data.chain_intact ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30" : "bg-rose-500/15 text-rose-300 ring-rose-500/30"}`}>
            {data.chain_intact ? "✓ chain intact" : "✗ chain broken"}
          </span>
        )}
        {data.count != null && <span className="text-xs text-slate-500">{data.count} events</span>}
      </div>

      <ol className="space-y-1">
        {data.events.map((e) => (
          <li key={e.seq} className="flex items-center gap-3 rounded bg-slate-900 px-3 py-2 text-sm ring-1 ring-slate-800">
            <span className="w-8 text-right text-xs text-slate-600">{e.seq}</span>
            <span className="w-52 font-mono text-xs text-cyan-300">{e.event}</span>
            <span className="flex-1 truncate text-slate-400">{e.trigger}</span>
            {e.firm && <span className="rounded bg-slate-800 px-2 py-0.5 text-xs">Firm {e.firm}</span>}
            <span className="text-xs text-slate-600">{e.retention}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
