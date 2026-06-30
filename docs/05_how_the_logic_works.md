# How the logic works — a plain-language tour

This is the doc to read before you defend the project. It explains, in everyday
language and tied to the real code, how a number gets from the source documents
to the report — and how each of the five constraints is enforced. If you can
re-tell the "worked example" below in your own words, you can defend the system.

---

## 1. The 30-second mental model

> The system reads a **rulebook** (the guidelines PDF) and a **list of holdings**
> (the CSV), stores the rules as a **graph of connected facts**, and then a plain
> **calculator** walks that graph to compute each figure. The AI only writes the
> English summary, and a **firewall** checks it never invented a number.

Everything else is detail in service of *proving* each number.

---

## 2. The pieces (what each folder does)

| Folder | Job | Key files / functions |
|---|---|---|
| `src/ingest/` | Read the inputs | `extract_holdings.load_positions()` (CSV → positions), `extract_guidelines.reextract()` (PDF → rules, optional, AI) |
| `data/extracted_graph.json` | The **frozen, human-approved** rules pulled from the PDF (with page/chunk/confidence on every item) | — |
| `src/review/gate.py` | The human-approval gate | `review_extraction()` |
| `src/graph/` | Store the rules+holdings as a graph and answer questions about it | `client.py` (`asset_class_view`, `non_ig_view`, `issuer_exposures`, …) |
| `src/config/` | Load a firm's method | `loader.load_config()` |
| `config/figures.yaml` + `firm_A.yaml`/`firm_B.yaml` | *Which* figures to compute, and *how* each firm computes them | — |
| `src/engine/` | **Compute every number** (no AI here) | `compute.compute_all()` + handlers, `format.py` |
| `src/narrative/` | AI writes prose, then we firewall it | `generate.py`, `firewall.check()` |
| `src/reconcile/` | Compare our numbers to the answer key | `reconciler.reconcile()` |
| `src/audit/` | Tamper-proof log of the run | `log.AuditLog` |
| `run.py` | Orchestrates the whole pipeline | `run_firm()` |

---

## 3. Follow ONE number end-to-end (the worked example)

Take **"Aggregate non-IG exposure"** — the percentage of the fund in
non-investment-grade assets. Under **Firm A** it's `15.0% — OK`. Here's exactly
how that happens, step by step:

1. **Start.** `run.py → run_firm("A")` loads Firm A's config, the frozen rules
   (`data/extracted_graph.json`), and the holdings, then builds the graph
   (`client.load(...)`).

2. **The engine loops over the 13 figures** (`engine/compute.py → compute_all`).
   For our figure, the catalogue (`config/figures.yaml`) says its `kind` is
   `aggregate_non_ig`, so the engine calls the handler `_h_aggregate_non_ig`.

3. **The handler asks the graph for its inputs** (this is the traceability):
   - `client.non_ig_view()` walks the graph: which asset classes
     **CONTRIBUTE_TO** the "non_ig" aggregate? → **High Yield** and **Structured
     Credit**. It also returns the **limit** (max 20%) and the **provenance**
     (guidelines PDF, page 2, chunk `chunk_2b71`).
   - Firm A's method is `non_ig_membership: asset_class`, so the handler sums the
     market values of positions whose asset class is High Yield or Structured
     Credit: `HY-01 5M + HY-02 4M + SC-01 6M = 15M`.

4. **The math** (plain `Decimal` arithmetic): `15M / 100M total × 100 = 15.0`.

5. **The handler returns the value plus its trail:** the `graph_path` string it
   just walked, and the `citation` (built from the provenance + the chunk's
   summary).

6. **Back in `_compute_one`, the value is formatted and judged:**
   - `format.render_value` → `"15.0%"`
   - `format.compute_status(15, {max: 20})` → 15 < 20 → `"OK"`
   - `format.render_utilization` → 15 / 20 = 0.75 → `"75.0%"`

7. **Output:** one JSON object with `value, status, limit, utilization,
   graph_path, citation`. That's one row of the report.

**Now switch to Firm B** and *only step 3 changes*: Firm B's method is
`non_ig_membership: rating_incl_fallen_angels`, so the handler *also* adds any
holding currently rated below investment grade — **Marina Bay Resorts (BB)**,
which sits in the IG-corporate class but was downgraded. That adds 6M →
`21M / 100M = 21.0%`, and `compute_status(21, {max: 20})` → 21 > 20 →
**BREACH**. Same code, different config line.

> If you can say steps 1–7 out loud, you understand the core of the assignment.

---

## 4. How each of the five constraints is enforced (and where)

**1. Reproducible (same inputs → identical numbers).**
We never let the computer's "fuzzy" decimal math or random ordering affect a
figure. All money math uses Python's exact `Decimal` type (`util.D`), rounding
happens in exactly one place with one rule (`util.quantize`), positions are
sorted by id, and timestamps are *frozen* in the data (not "now"). So running
twice gives byte-identical output. *Proof:* `run.py --firm A` twice and `diff`.

**2. Traceable through the graph.**
Every figure's *inputs* come from a graph query (`client.*_view`,
`issuer_exposures`), and each figure emits the `graph_path` it walked plus a
`citation` to the exact PDF passage. The provenance (`source_doc, page,
chunk_id`) lives on the graph nodes themselves, so the citation isn't made up —
it's read from the same node that gave us the limit. If a figure *can't* be
traced, `_compute_one` catches the error and returns `status: ERROR` instead of
a number (see `TraceError`).

**3. The AI can't produce a number.**
Two walls. First, the engine code (`src/engine/`) never imports an AI client —
there's no path from a figure to the model. Second, the AI narrative is checked
by `narrative/firewall.check()`: it pulls every number out of the AI's text and
rejects any that isn't already in the computed figures. If the AI sneaks a
number in, we throw its text away and use a safe template instead. *Proof:* the
`FIREWALL_CHECK` audit event shows `passed: true`.

**4. Reproduce Firm A's answer key.**
`reconcile/reconciler.py` reads `firm_A_answer_key.xlsx`, matches rows by metric
name, and compares **Value, Limit, Status** exactly. All 13 match.

**5. Reconfigure to Firm B with no code edit.**
A firm's method is three knobs in `config/firm_B.yaml`
(`non_ig_membership`, `gre_grouping`, `utilization_format`). The engine already
contains *both* options for each knob; the config just selects one. Switching
firms = loading a different YAML file. *Proof:* `run.py --firm A` then
`--firm B`, no code touched, three figures change.

**Append-only audit log.**
`audit/log.py` writes every step to SQLite. UPDATE and DELETE are blocked by
database triggers, and each row stores a hash of (previous row + this row), so
editing history breaks the chain. `verify_chain()` checks it.

---

## 5. Design FAQ

Common questions about how the system meets its requirements:

- **How is a figure traced to its source?** → See the §3 example: non-IG 15%
  comes from High Yield + Structured Credit positions; the graph path runs
  through the `non_ig` aggregate to the limit; the citation resolves to
  guidelines p.2. Every figure emits `value + graph_path + citation`.
- **How is the LLM prevented from producing a number?** → The engine never
  imports the LLM; the LLM only writes prose; the firewall rejects any number in
  that prose that the engine didn't produce (§4, constraint 3).
- **How do I produce Firm B's figures?** → Load `firm_B.yaml` (three method
  knobs); run `--firm B`. No engine edit — non-IG and GRE flip to BREACH.
- **Is the output deterministic?** → `Decimal` arithmetic + a single rounding
  rule + frozen timestamps; run twice and diff the JSON to confirm byte-identical
  output (`tests/test_constraints.py::test_reproducible_byte_identical`).
- **Why a knowledge graph instead of computing directly from the CSV?** → Because
  every figure's inputs are pulled from graph nodes that carry their own
  source/page provenance, so the `figure → graph path → source` chain is real,
  not decorative — and multi-hop questions are answered by traversal.
- **What are the known limitations?** → The guidelines extraction is
  AI-assisted, human-approved, and frozen; production hardening (auth, a managed
  graph DB, broader rating/currency modelling) is out of scope. See
  `docs/06_notes_and_reflections.md`.

---

## 6. Glossary (the scary words, in plain English)

- **Knowledge graph** — facts stored as dots (nodes) connected by labelled lines
  (edges). E.g. *High Yield Bonds —has limit→ max 15%*.
- **Node / edge** — a dot / a connecting line.
- **Cypher** — the query language for graphs (the `(A)-[:REL]->(B)` syntax).
- **Provenance** — where a fact came from (document, page, chunk, confidence).
- **Decimal** — exact decimal arithmetic (avoids `0.1 + 0.2 = 0.30000004`).
- **NAV** — Net Asset Value, the fund's total value (here SGD 100M).
- **Basis point (bps)** — 1/100th of a percent. 6000 bps = 60%. Firm B reports
  utilization this way.
- **Fallen angel** — a bond downgraded from investment-grade to below it (e.g.
  Marina Bay BB, was BBB-).
- **GRE** — Government-Related Entity (e.g. Redhill Power); capped at 12%.
- **Modified duration / DV01** — interest-rate risk measures; DV01 ≈ how much
  value changes for a 1bp rate move.
- **Reconciliation** — checking our numbers against the official answer key.
- **Hash chain** — each log row carries a fingerprint of the previous one, so
  tampering with history is detectable.
