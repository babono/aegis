const STYLES: Record<string, string> = {
  OK: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  BREACH: "bg-rose-500/15 text-rose-300 ring-rose-500/30",
  "AT LIMIT": "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  ERROR: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
};

export function StatusBadge({ status }: { status: string | null }) {
  const s = status ?? "ERROR";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${STYLES[s] ?? STYLES.ERROR}`}>
      {s}
    </span>
  );
}

export function PassFail({ result }: { result: string | null | undefined }) {
  if (!result) return <span className="text-slate-500">—</span>;
  const ok = result === "PASS";
  return (
    <span className={ok ? "text-emerald-400" : "text-rose-400"}>
      {ok ? "✓ pass" : `✗ ${result.toLowerCase()}`}
    </span>
  );
}
