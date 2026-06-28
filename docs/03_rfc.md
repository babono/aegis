# RFC — Audit-Defensible Compliance Reporting

**Status:** implemented · **Audience:** engineering + audit reviewer

This memo derives the architecture from the five hard constraints. The finance
math in this assignment is small; the engineering problem is *provenance* — being
able to prove, to an examiner, how each number was produced. Every decision below
is in service of that.

---

## 1. The core decision: the graph is the single source of truth, the engine is the only producer

Two failure modes dominate this domain: a number whose origin can't be shown, and
a number an LLM invented. We eliminate both with one structural choice:

> **All inputs to a figure come from the knowledge graph; all figures come from a
> deterministic engine; the LLM is downstream of both and may only emit prose that
> is validated against the engine's numbers.**

Everything else follows from this.

## 2. Constraint 3 — why the LLM *cannot* be the source of any number

We treat constraint 3 as a structural property, not a prompt instruction. Three
independent barriers:

1. **Module boundary.** The computation packages (`src/engine`, `src/graph`,
   `src/reconcile`) never import an LLM client. The LLM client lives only in
   `src/narrative`. This is verifiable by `grep`: there is no path from a figure
   to the model.
2. **Direction of data flow.** The narrative function *receives* the already-computed
   figures and *returns text*. It is architecturally incapable of feeding a value
   back into a figure — figures are written to `figures.json` and the report before
   the narrative runs.
3. **The firewall, verified not asserted.** `src/narrative/firewall.py` tokenizes
   every number out of the narrative and asserts each is a member of the set of
   numbers the engine produced. If the narrative introduces a number (a
   hallucinated return, a re-rounded percentage), the firewall fails, the LLM
   narrative is **rejected**, and a safe deterministic narrative is substituted.
   The check is logged (`FIREWALL_CHECK`) so an examiner can replay it.

Why a firewall rather than "just trust temperature=0"? Because trust isn't
auditable. A reviewer can run `--evaluate` and see `firewall.passed == true` with
the allowed-number count — a mechanical proof, reproducible on their machine.

*Extraction is the subtle case.* Extracting limits from the PDF is LLM-assisted,
which looks like the LLM touching numbers. We resolve it by (a) making extraction a
one-time, **human-gated** step whose output is frozen in `data/extracted_graph.json`,
and (b) having the deterministic engine read only that approved file. The LLM
*proposes* structure; a human *approves* it against the source; the engine *computes*
from the approved graph. The LLM is never in the path that computes a reported figure.

## 3. Constraint 2 — how a figure traces to its source through the graph

Each figure is computed by a handler that **queries the graph for its inputs** and
builds its `graph_path` from the entities it actually traversed. The emitted shape:

```json
{
  "figure": "aggregate_non_ig_exposure",
  "value": "15.0%", "status": "OK", "limit": "max 20%",
  "graph_path": "(Aggregate:non_ig)<-[:CONTRIBUTES_TO]-(AssetClass:high_yield)<-[:CONTRIBUTES_TO]-(AssetClass:structured_credit)-[:HAS_LIMIT]->(Limit)",
  "citation": {"source_doc": "sample_fund_guidelines.pdf", "page": 2,
               "chunk_id": "chunk_2b71", "passage_summary": "Section 2 — aggregate non-IG cap"}
}
```

Provenance is carried on **every node and edge** (`source_doc, page, chunk_id,
ingested_at, extraction_confidence`), so the citation is read from the same graph
element that supplied the limit — not re-derived. **A figure that cannot resolve
`figure → graph_path → source` is returned with `status: ERROR`, never a silent
number.** The traceability check in `--evaluate` enforces this for every row.

Design note: the graph is genuinely on the compute path. We deliberately did *not*
compute figures from the CSV/PDF directly and decorate them with a graph picture —
that is the explicit anti-pattern the brief calls a fail. `total_nav()`,
`asset_class_view()`, `issuer_exposures()` etc. are graph queries; the engine only
does Decimal arithmetic over what they return.

## 4. Constraint 5 — how a firm's method is expressed and switched

A firm's method is **data**, not code. Three switch-points cover every difference
between Firm A and Firm B, each a named strategy the engine already implements:

| Knob | Firm A | Firm B |
|---|---|---|
| `non_ig_membership` | `asset_class` | `rating_incl_fallen_angels` |
| `gre_grouping` | `issuer` | `parent_issuer` |
| `utilization_format` | `percent_1dp` | `truncated_bps` |

The engine contains *both* branches of each knob; `config/firm_X.yaml` selects one.
Switching firms loads a different YAML — **no engine edit**, which the grader checks
by running `--firm A` then `--firm B`. A Firm-A-baked implementation would need a
code change to produce Firm B; this design cannot, because there is no firm-specific
constant anywhere in `src/`. The loader validates the selected values, so an invalid
method fails loudly instead of silently emitting the wrong firm's numbers.

Why config over a plugin/inheritance scheme? For three knobs over one fund, a
declarative config is the smallest thing that is also fully auditable — the diff
between `firm_A.yaml` and `firm_B.yaml` *is* the documentation of how the firms
differ. (A small DSL is the natural next step and is noted as bonus scope.)

## 5. Constraint 4 — how output is reconciled to an answer key

`src/reconcile/reconciler.py` reads `firm_A_answer_key.xlsx`, maps rows by
`(Section, Metric)`, and diffs the substantive columns **Value, Limit, Status** with
a numeric delta per figure. Firm B's key is Firm A's with the rows the brief states
overridden (`data/firm_B_expected_overrides.json`, sourced from `firm_B_brief.md`).

**Tolerance:** we reconcile **exactly** (zero tolerance) on Value/Limit/Status for
all 13 figures of both firms — every figure is hand-derivable from the inputs and
NAV is a round SGD 100M, so there is no rounding ambiguity to absorb. Utilization is
*representational* (percent for A, truncated bps for B), so it is reported but not
diffed across formats; this is the one place a format, not a value, differs.

## 6. Determinism (constraint 1) — mechanics

`Decimal` via `str()` coercion (no binary-float artifacts); a single rounding policy
(`ROUND_HALF_UP`, or `ROUND_DOWN` for truncated bps) applied in one place
(`engine/format.py`); positions sorted by id; graph queries `ORDER BY`; ingestion
timestamps frozen in the approved extraction; JSON serialized with `sort_keys`. The
test `test_reproducible_byte_identical` and the docker run (`run twice, diff`) both
confirm byte-identical figures.

## 7. Key trade-offs and what we'd add for production

- **Neo4j + embedded fallback.** Neo4j gives real Cypher and an inspectable graph;
  the embedded backend keeps the system runnable and testable without a container.
  Both honor one interface so figures are backend-independent.
- **Frozen approved extraction.** Trades "always re-extract" for reproducibility and
  zero-key reproducibility. Re-extraction is available behind `--re-extract` and the
  gate.
- **Production gaps (out of scope, by the brief):** real auth/RBAC on the audit DB,
  secrets in a vault rather than env, the audit log in an append-only store (e.g.
  QLDB / object-lock S3) rather than SQLite, signed report exports, and a fuller
  rating-scale / cross-currency model. Error handling here covers the happy path
  plus two failure modes the brief names: a low-confidence extraction held at the
  gate, and an untraceable figure returned as `ERROR`.

## 8. What an examiner does, and what they see

1. **Run twice, diff** → identical `figures_firm_A.json` (constraint 1).
2. **Trace one figure** → `graph_path` + `citation` on every row; `--evaluate`
   shows `all_traceable=true` (constraint 2).
3. **`--firm A` then `--firm B`, no edit** → three figures change; `firewall.passed`
   stays true (constraints 3, 5).
4. **Replay the audit log** → hash-chained events for graph build, every figure,
   reconciliation, config change, export; UPDATE/DELETE blocked by the database.
