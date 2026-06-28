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
      <p className="text-sm text-slate-400">
        Switching firms swaps a config file — no engine code changes. The highlighted rows differ.
      </p>
      <table className="w-full overflow-hidden rounded-lg text-sm ring-1 ring-slate-800">
        <thead className="bg-slate-900 text-left text-slate-400">
          <tr>
            <th className="px-4 py-2">Method knob</th>
            <th className="px-4 py-2">Firm A</th>
            <th className="px-4 py-2">Firm B</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const av = a?.methods[k] ?? "—";
            const bv = b?.methods[k] ?? "—";
            const diff = av !== bv;
            return (
              <tr key={k} className={`border-t border-slate-800 ${diff ? "bg-indigo-500/5" : ""}`}>
                <td className="px-4 py-2 font-mono text-xs text-slate-300">{k}</td>
                <td className="px-4 py-2">{av}</td>
                <td className={`px-4 py-2 ${diff ? "font-semibold text-indigo-300" : ""}`}>{bv}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="grid gap-4 md:grid-cols-2">
        {[a, b].map((c, i) => (
          <div key={i}>
            <p className="mb-1 text-xs uppercase text-slate-500">{c?.name ?? `Firm ${i ? "B" : "A"}`}</p>
            <pre className="overflow-x-auto rounded bg-slate-950 p-3 text-xs text-slate-300 ring-1 ring-slate-800">{c?.yaml ?? "…"}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
