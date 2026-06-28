"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Cfg { firm: string; yaml: string; methods: Record<string, string>; name: string }

// Side-by-side firm methods — the entire difference between reproducing Firm A's
// and Firm B's answer keys lives here, not in engine code.
export function ConfigPanel() {
  const [a, setA] = useState<Cfg | null>(null);
  const [b, setB] = useState<Cfg | null>(null);

  useEffect(() => {
    api.config("A").then(setA).catch(() => {});
    api.config("B").then(setB).catch(() => {});
  }, []);

  const keys = ["non_ig_membership", "gre_grouping", "utilization_format"];

  return (
    <div className="space-y-5">
      <p className="text-sm text-ink-2">
        Switching firms swaps a config file — no engine code changes. The highlighted rows differ.
      </p>
      <div className="overflow-hidden rounded-lg border border-line">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft text-left text-ink-2">
            <tr>
              <th className="px-4 py-2 font-semibold">Method knob</th>
              <th className="px-4 py-2 font-semibold">Firm A</th>
              <th className="px-4 py-2 font-semibold">Firm B</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => {
              const av = a?.methods[k] ?? "—";
              const bv = b?.methods[k] ?? "—";
              const diff = av !== bv;
              return (
                <tr key={k} className={`border-t border-line ${diff ? "bg-primary-soft/50" : "bg-bg"}`}>
                  <td className="px-4 py-2 font-mono text-xs text-ink-1">{k}</td>
                  <td className="px-4 py-2 text-ink-1">{av}</td>
                  <td className={`px-4 py-2 ${diff ? "font-bold text-road-text" : "text-ink-1"}`}>{bv}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {[a, b].map((c, i) => (
          <div key={i}>
            <p className="mb-1 text-xs font-semibold uppercase text-ink-3">{c?.name ?? `Firm ${i ? "B" : "A"}`}</p>
            <pre className="overflow-x-auto rounded border border-line bg-bg-soft p-3 text-xs text-ink-1">{c?.yaml ?? "…"}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
