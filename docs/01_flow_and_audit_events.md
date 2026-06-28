# Phase 1 — Reporting Flow & Audit-Event Catalogue

## 1. AS-IS flow (manual, today)

```
Analyst reads guidelines PDF ─► eyeballs holdings spreadsheet ─► types formulas
   into working tabs ─► copies results into a report template ─► emails report
```

Failure modes this produces:
- **Not reproducible** — a formula edited in one tab silently changes a figure.
- **Not traceable** — "where did this number come from?" → a buried cell reference.
- **No firewall** — a hand-typed number can be anything; nothing proves provenance.
- **Not reconfigurable** — Firm B's conventions mean re-deriving by hand.

## 2. TO-BE flow (this system)

Legend: ⚙️ = autonomous/deterministic · 🧠 = LLM (narrative only) · 🧑 = human gate.

```
                 ┌──────────────────────────────────────────────────────────┐
   guidelines    │  🧠 LLM-assisted extraction  ─►  candidate graph + conf.  │
   PDF ──────────►  (only on --re-extract)                                    │
                 └───────────────────────────────┬──────────────────────────┘
                                                 ▼
                                   🧑 GATE 1: graph review  ───────────────┐
                                   (auto-pass vs human review)             │ fail → HUMAN_REVIEW,
                                                 │ pass                     │ run aborts (exit 2)
                                                 ▼                          │
   holdings CSV ──► ⚙️ deterministic parse ──►  ⚙️ build knowledge graph (Neo4j)
                                                 │
                                                 ▼
   firm_X.yaml ──► ⚙️ compute figures by GRAPH TRAVERSAL (Decimal, no LLM)
                                                 │
                         ┌───────────────────────┼───────────────────────┐
                         ▼                        ▼                       ▼
              ⚙️ reconcile vs answer key   🧠 narrative (prose)    ⚙️ figures.json
                         │                        │                       │
                         │                        ▼                       │
                         │              ⚙️ FIREWALL: reject any number ────┤
                         │                 not in computed figures        │
                         ▼                        ▼                       ▼
                                   🧑 GATE 2: report sign-off
                                   (auto-pass vs human review)
                                                 │ pass
                                                 ▼
                                   ⚙️ export report.xlsx + audit log
```

### Gate criteria (auto-pass vs. human review)

| Gate | Decision criterion (auto-pass) | Else |
|---|---|---|
| **Gate 1 — graph review** (`src/review/gate.py`) | Every node/edge `extraction_confidence ≥ 0.75` **and** `extraction_method == llm_assisted_human_approved` **and** an approver is recorded. | Route to **HUMAN_REVIEW**; run aborts. The committed extraction is pre-approved so normal runs auto-pass; a fresh `--re-extract` candidate is held. |
| **Gate 2 — report sign-off** | Reconciliation `all_passed == true` **and** firewall `passed == true` **and** every figure is traceable (`figure → graph_path → source`). | Route to human review; do not distribute. |

The graph-review gate exists because entity/relationship extraction is error-prone:
the system must not trust extracted numbers until a human has verified them against
the source passages. After approval, **the numbers are frozen** — the deterministic
engine reads only the approved graph, never the LLM.

## 3. The LLM ↔ deterministic boundary (heart of constraint 3)

| May be **LLM-generated** | Must be **deterministic** |
|---|---|
| Narrative/commentary prose (`src/narrative/generate.py`). | Every reported number: value, limit, utilization, status. |
| *Candidate* entity/relationship extraction, **only** as a proposal that a human must approve at Gate 1. | The knowledge graph's trusted contents (post-approval). |
| Wording of breach explanations — restating computed facts. | All figure computation (`src/engine/`), rounding, formatting. |
| | Reconciliation, traceability, the firewall check, the audit log. |

Enforcement is **structural, not aspirational**: the engine modules never import an
LLM client; the narrative receives figures as read-only input and emits text; that
text is passed through the firewall (`src/narrative/firewall.py`), which **rejects
any numeric token not already present in the computed figures**. A number therefore
cannot enter a report from the LLM.

## 4. Audit-event catalogue

Every event is appended to a write-once, hash-chained log (`src/audit/log.py`).
Retention classes follow the guidelines §5.1 (7y transaction data / 10y investor-facing).

| Event | Trigger | Data captured | Retention |
|---|---|---|---|
| `CONFIG_CHANGE` | A firm config is loaded (`--firm A/B`) | firm name, selected `methods`, config file paths | 7y |
| `GRAPH_REVIEW_GATE` | Extraction ingested, before trust | gate decision, reasons, low-confidence items, threshold | 10y |
| `RUN_ABORTED` | Gate held for human review | gate decision + reasons | 10y |
| `GRAPH_CONSTRUCTED` | Approved graph built into the store | backend, node/edge/position counts, `graph_hash` | 7y |
| `FIGURE_COMPUTED` | Each figure produced | figure id, value, status, limit, utilization, **graph_path, citation** | 7y |
| `FIREWALL_CHECK` | Narrative generated | narrative source, passed/violations, whether LLM narrative was rejected | 7y |
| `RECONCILIATION` | Figures compared to answer key | passed/failed counts, all_passed | 7y |
| `REPORT_EXPORTED` | Report + figures bundle written | output file paths | 10y |

Each row stores `prev_hash` and `row_hash = SHA256(prev_hash + canonical(payload))`.
`verify_chain()` recomputes the chain end-to-end; altering any historical row breaks
every subsequent hash, so tampering is detectable as well as forbidden. UPDATE and
DELETE are additionally blocked by database triggers (`RAISE(ABORT)`).
