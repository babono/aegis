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
    <div className="mt-4 rounded-lg border border-line bg-bg">
      <button
        onClick={toggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm font-bold text-ink-0">
          What am I looking at? <span className="font-normal text-ink-3">— how to read this report</span>
        </span>
        <span className="text-ink-3">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="space-y-4 border-t border-line px-4 py-4 text-sm text-ink-1">
          <p>
            A fund holds a portfolio of bonds and must follow a rulebook (allocation limits,
            risk caps, liquidity floors). This is the <strong>report card</strong>: for every
            rule, is the fund inside its limit or breaking it — and can every number be proven?
          </p>

          <div>
            <p className="mb-1 font-bold text-ink-0">How to read a row</p>
            <ul className="ml-4 list-disc space-y-1 text-ink-2">
              <li><b className="text-ink-0">Value</b> — what the fund actually is (e.g. 9% in high-yield bonds).</li>
              <li><b className="text-ink-0">Limit</b> — what the rule allows (e.g. max 15%).</li>
              <li><b className="text-ink-0">Utilization</b> — how much of the limit is used. Firm A shows % (60.0%); Firm B shows basis points (6000 bps = 60%).</li>
              <li><b className="text-ink-0">Status</b> — the verdict. <b className="text-ok-text">OK</b> within limit · <b className="text-warn-text">AT LIMIT</b> exactly at it · <b className="text-danger-text">BREACH</b> outside it.</li>
              <li><b className="text-ink-0">vs key</b> — matches the official answer key.</li>
            </ul>
          </div>

          <div>
            <p className="mb-1 font-bold text-ink-0">Click any row</p>
            <p className="text-ink-2">
              to see its <b>proof</b>: the path through the knowledge graph, the exact source
              passage in the guidelines PDF, the difference vs the answer key, and which firm
              rule produced it.
            </p>
          </div>

          <div>
            <p className="mb-1 font-bold text-ink-0">Why it&apos;s trustworthy (the 5 guarantees)</p>
            <ul className="ml-4 list-disc space-y-1 text-ink-2">
              <li><b className="text-ink-0">Reproducible</b> — same inputs always give the same numbers.</li>
              <li><b className="text-ink-0">Traceable</b> — every number links back to the rulebook passage it came from.</li>
              <li><b className="text-ink-0">No AI numbers</b> — figures come from a deterministic engine; the AI only writes the summary, and a firewall blocks any number it invents.</li>
              <li><b className="text-ink-0">Matches the answer key</b> — reconciles exactly to the expected report.</li>
              <li><b className="text-ink-0">Firm-switchable</b> — flip Firm A→B and 3 numbers change, by configuration only (no code change).</li>
            </ul>
          </div>

          <p className="rounded border border-road-line bg-road-bg px-3 py-2 text-xs text-road-text">
            Try it: switch <b>Firm A → Firm B</b> above and watch &ldquo;Aggregate non-IG exposure&rdquo;
            and &ldquo;Largest GRE issuer&rdquo; flip to BREACH — Firm B counts them differently.
          </p>
        </div>
      )}
    </div>
  );
}
