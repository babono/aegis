"use client";
import { useEffect, useState } from "react";
import { api, AuditResponse } from "@/lib/api";

export function AuditPanel() {
  const [data, setData] = useState<AuditResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.audit().then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="text-danger-text">{err}</p>;
  if (!data) return <p className="text-ink-3">Loading audit log…</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-sm text-ink-2">Append-only · hash-chained · UPDATE/DELETE blocked</span>
        {data.chain_intact === null ? (
          <span className="rounded-full bg-bg-muted px-3 py-1 text-xs text-ink-2">no log yet — run the pipeline</span>
        ) : (
          <span className={`rounded-full px-3 py-1 text-xs font-bold ring-1 ${data.chain_intact ? "bg-ok-bg text-ok-text ring-ok-line" : "bg-danger-bg text-danger-text ring-danger-line"}`}>
            {data.chain_intact ? "✓ chain intact" : "✗ chain broken"}
          </span>
        )}
        {data.count != null && <span className="text-xs text-ink-3">{data.count} events</span>}
      </div>

      <ol className="space-y-1">
        {data.events.map((e) => (
          <li key={e.seq} className="flex items-center gap-3 rounded border border-line bg-bg px-3 py-2 text-sm">
            <span className="w-8 text-right text-xs text-ink-4">{e.seq}</span>
            <span className="w-52 font-mono text-xs font-semibold text-primary">{e.event}</span>
            <span className="flex-1 truncate text-ink-2">{e.trigger}</span>
            {e.firm && <span className="rounded bg-bg-muted px-2 py-0.5 text-xs text-ink-2">Firm {e.firm}</span>}
            <span className="text-xs text-ink-4">{e.retention}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
