"use client";
import { useEffect, useState } from "react";

// Plain-language explainer so a first-time visitor understands the dashboard
// without domain knowledge. Collapses after first view (remembered locally).
export function HowItWorks() {
  const [open, setOpen] = useState(true);

  useEffect(() => {
    setOpen(localStorage.getItem("hiw_dismissed") !== "1");
  }, []);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    localStorage.setItem("hiw_dismissed", next ? "0" : "1");
  };

  return (
    <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/60">
      <button
        onClick={toggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm font-semibold">
          ℹ️ What am I looking at? <span className="font-normal text-slate-500">— how to read this report</span>
        </span>
        <span className="text-slate-500">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="space-y-4 border-t border-slate-800 px-4 py-4 text-sm text-slate-300">
          <p>
            A fund holds a portfolio of bonds and must follow a rulebook (allocation limits,
            risk caps, liquidity floors). This is the <strong>report card</strong>: for every
            rule, is the fund inside its limit or breaking it — and can every number be proven?
          </p>

          <div>
            <p className="mb-1 font-semibold text-slate-200">How to read a row</p>
            <ul className="ml-4 list-disc space-y-1 text-slate-400">
              <li><b className="text-slate-200">Value</b> — what the fund actually is (e.g. 9% in high-yield bonds).</li>
              <li><b className="text-slate-200">Limit</b> — what the rule allows (e.g. max 15%).</li>
              <li><b className="text-slate-200">Utilization</b> — how much of the limit is used. Firm A shows % (60.0%); Firm B shows basis points (6000 bps = 60%).</li>
              <li><b className="text-slate-200">Status</b> — the verdict. <b className="text-emerald-300">OK</b> within limit · <b className="text-amber-300">AT LIMIT</b> exactly at it · <b className="text-rose-300">BREACH</b> outside it.</li>
              <li><b className="text-slate-200">vs key</b> — matches the official answer key.</li>
            </ul>
          </div>

          <div>
            <p className="mb-1 font-semibold text-slate-200">Click any row</p>
            <p className="text-slate-400">
              to see its <b>proof</b>: the path through the knowledge graph, the exact source
              passage in the guidelines PDF, the difference vs the answer key, and which firm
              rule produced it.
            </p>
          </div>

          <div>
            <p className="mb-1 font-semibold text-slate-200">Why it&apos;s trustworthy (the 5 guarantees)</p>
            <ul className="ml-4 list-disc space-y-1 text-slate-400">
              <li><b className="text-slate-200">Reproducible</b> — same inputs always give the same numbers.</li>
              <li><b className="text-slate-200">Traceable</b> — every number links back to the rulebook passage it came from.</li>
              <li><b className="text-slate-200">No AI numbers</b> — figures come from a deterministic engine; the AI only writes the summary, and a firewall blocks any number it invents.</li>
              <li><b className="text-slate-200">Matches the answer key</b> — reconciles exactly to the expected report.</li>
              <li><b className="text-slate-200">Firm-switchable</b> — flip Firm A→B and 3 numbers change, by configuration only (no code change).</li>
            </ul>
          </div>

          <p className="text-xs text-slate-500">
            Try it: switch <b>Firm A → Firm B</b> above and watch &ldquo;Aggregate non-IG exposure&rdquo;
            and &ldquo;Largest GRE issuer&rdquo; flip to BREACH — Firm B counts them differently.
          </p>
        </div>
      )}
    </div>
  );
}
