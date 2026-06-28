# Meridian Compliance Reporting — InterOpera Take-Home

An audit-defensible system that produces a regulatory compliance report for the
Meridian Fixed Income Fund. It turns a guidelines PDF + a holdings snapshot into a
report where **every figure is reproducible, traceable through a knowledge graph to
its source passage, and provably not produced by a language model** — and where the
same engine reproduces a second firm's answer key by configuration alone.

## Quick start

### Option A — docker compose (recommended; uses Neo4j)

```bash
docker compose up --build
```

This starts Neo4j, waits for it, then runs the **whole assessment**: Firm A's
report, Firm B's report (no code edit between them), and the Phase 5 evaluation.
Outputs land in `./output/` and the audit log in `./audit/audit.db`.

### Option B — no container (embedded graph backend)

```bash
pip install -r requirements.txt
python run.py --firm A            # Firm A report  -> output/
python run.py --firm B            # Firm B report  (config only, no code edit)
python run.py --evaluate          # Phase 5: reconciliation + traceability + firewall
```

No API key is required: every figure is produced by the deterministic engine. The
LLM is used only for narrative prose and falls back to a deterministic mock when
`DEEPSEEK_API_KEY` is unset.

## Web product (optional — the "cherry on top")

A Next.js + Tailwind dashboard over a FastAPI wrapper of the **same engine** (it
computes nothing new — it serves what the deterministic engine produced). The
graded core command above is unaffected; the web stack is opt-in.

```bash
# Everything in containers (core pipeline + API + dashboard):
docker compose --profile web up --build
# open http://localhost:3000
```

Or run the two dev servers directly:

```bash
# backend
pip install -r requirements-web.txt
uvicorn api.main:app --reload --port 8000
# frontend (in another shell)
cd web && npm install && npm run dev      # open http://localhost:3000
```

The dashboard: pick **Firm A / B** and watch three figures change (config only);
click any figure for its **trace** (graph path → source citation, delta vs the
answer key, and which config rule produced it); inspect the **append-only audit
log**; and compare the two firms' **method configs** side by side.

**Deployment (live demo).** Frontend → Vercel (set `NEXT_PUBLIC_API_BASE` to the
backend URL). Backend → Render via `render.yaml` (FastAPI + embedded graph, no DB
to host). The local `docker compose up` still uses Neo4j; the hosted API uses the
embedded twin, which returns identical numbers.

## What you get (in `output/`)

| File | Contents |
|---|---|
| `report_firm_A.xlsx` / `report_firm_B.xlsx` | The populated report template, incl. a `graph_path → source` cell per figure and a separate Narrative sheet. |
| `figures_firm_A.json` / `figures_firm_B.json` | Machine-readable per-figure bundle: value, status, limit, utilization, **graph_path, citation**, plus reconciliation + firewall results. |
| `evaluation.json` | Phase 5: per-figure reconciliation, traceability, firewall. |
| `audit/audit.db` | Append-only, hash-chained audit log of the run. |

## Verifying the five constraints yourself

```bash
# 1. Reproducible — run twice, figures are byte-identical
python run.py --firm A && cp output/figures_firm_A.json /tmp/a1.json
python run.py --firm A && diff /tmp/a1.json output/figures_firm_A.json   # (no output)

# 2. Traceable through the graph — every figure has graph_path + citation
python run.py --evaluate            # all_traceable=true
python run.py --multihop-demo       # multi-hop graph query demo

# 3 + 4 + 5. firewall passes; Firm A reconciles; Firm B reconciles by config only
python run.py --firm A && python run.py --firm B && python run.py --evaluate

# All constraints as automated tests:
pip install pytest && PYTHONPATH=. pytest tests/ -q
```

## How it works (one paragraph)

A human-approved extraction of the guidelines (`data/extracted_graph.json`, carrying
provenance + confidence on every node/edge) and the holdings CSV are loaded into a
**knowledge graph** (Neo4j, or an embedded backend without Docker). A **deterministic
engine** (`src/engine/`) computes each figure by *traversing the graph* for its
inputs and applying `Decimal` arithmetic — the LLM is never on this path. Each figure
emits its value, its `graph_path`, and its source `citation`; an untraceable figure is
returned as `ERROR`. A firm's house conventions live entirely in `config/firm_*.yaml`,
so switching from Firm A to Firm B is a config swap with **no engine edit**. The LLM
writes only narrative, and a **firewall** rejects any number it introduces that the
engine did not compute. Every step is appended to a hash-chained, UPDATE/DELETE-proof
audit log.

See `docs/` for the flow + audit catalogue (`01`), architecture (`02`), and the RFC
(`03`) that derives the design from the constraints.

## Repository layout

```
run.py                     single entrypoint (pipeline / evaluate / demos)
config/
  figures.yaml             shared, firm-agnostic figure catalogue (13 report rows)
  firm_A.yaml firm_B.yaml  per-firm method knobs (the only A/B difference)
data/
  extracted_graph.json     human-approved guidelines extraction (provenance + conf.)
  firm_B_expected_overrides.json   Firm B answer-key deltas (from firm_B_brief.md)
src/
  ingest/    holdings parse (deterministic) + guidelines extraction (LLM, gated)
  review/    human approval gate for the extracted graph
  graph/     Neo4j + embedded backends, multi-hop queries
  engine/    deterministic figure computation + formatting  (NO LLM)
  config/    firm-method loader + validation
  narrative/ LLM narrative (DeepSeek) + the number firewall
  reconcile/ diff vs answer keys
  report/    xlsx writer
  audit/     append-only, hash-chained log
docs/        01 flows + audit events · 02 architecture · 03 RFC
tests/       one test per constraint + append-only audit
sample_docs/ provided materials
```

## LLM provider

The narrative layer uses **DeepSeek** (OpenAI-API-compatible) via the `openai` SDK
pointed at `https://api.deepseek.com`. Set `DEEPSEEK_API_KEY` (or copy `.env.example`
to `.env`) to enable it. It is **optional and firewalled** — numbers never depend on
it. Any frontier provider could be swapped in by changing only `src/narrative/`.

## Notes

- **Security/scale:** per the brief, no production auth/secrets; designed for the
  sample materials. Production gaps are listed in `docs/03_rfc.md §7`.
- **Determinism vs. timestamps:** ingestion timestamps are frozen in the approved
  extraction and the run clock defaults to a fixed value (`RUN_TS`) so even the audit
  log is replayable; reported figures carry no timestamp.
