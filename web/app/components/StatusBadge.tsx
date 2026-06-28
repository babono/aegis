const STYLES: Record<string, string> = {
  OK: "bg-ok-bg text-ok-text ring-ok-line",
  BREACH: "bg-danger-bg text-danger-text ring-danger-line",
  "AT LIMIT": "bg-warn-bg text-warn-text ring-warn-line",
  ERROR: "bg-bg-muted text-ink-2 ring-line-dark",
};

export function StatusBadge({ status }: { status: string | null }) {
  const s = status ?? "ERROR";
  return (
    <span className={`inline-flex items-center rounded px-2.5 py-0.5 text-xs font-bold ring-1 ${STYLES[s] ?? STYLES.ERROR}`}>
      {s}
    </span>
  );
}

export function PassFail({ result }: { result: string | null | undefined }) {
  if (!result) return <span className="text-ink-4">—</span>;
  const ok = result === "PASS";
  return (
    <span className={ok ? "font-semibold text-ok-text" : "font-semibold text-danger-text"}>
      {ok ? "✓ pass" : `✗ ${result.toLowerCase()}`}
    </span>
  );
}
