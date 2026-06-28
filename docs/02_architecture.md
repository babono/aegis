# Phase 1 — Architecture

## Component diagram

```mermaid
flowchart TD
    subgraph Sources
        G[sample_fund_guidelines.pdf]
        H[sample_holdings.csv]
        AK[firm_A_answer_key.xlsx]
        FB[firm_B_brief.md]
    end

    subgraph Ingestion
        EX[extract_guidelines.py\nLLM-assisted • on --re-extract]
        EH[extract_holdings.py\ndeterministic parse]
        GATE[review/gate.py\nhuman approval gate]
        EG[(data/extracted_graph.json\nFROZEN • human-approved\nprovenance + confidence)]
    end

    subgraph Graph["Knowledge Graph (constraint 2)"]
        NEO[(Neo4j\nor embedded fallback)]
    end

    subgraph Config["Firm method (constraint 5)"]
        FCAT[config/figures.yaml\nshared catalogue]
        FA[config/firm_A.yaml]
        FBY[config/firm_B.yaml]
    end

    subgraph Engine["Deterministic engine (constraints 1,3)"]
        COMP[engine/compute.py\nDecimal • graph traversal\nNO LLM]
        FMT[engine/format.py]
    end

    subgraph Narrative["LLM layer (constraint 3 firewall)"]
        NAR[narrative/generate.py\nDeepSeek • prose only]
        FW[narrative/firewall.py\nrejects new numbers]
    end

    subgraph Outputs
        FIG[output/figures_firm_X.json]
        REP[output/report_firm_X.xlsx]
        REC[reconcile/reconciler.py\nvs answer key • constraint 4]
        EVAL[output/evaluation.json\nPhase 5]
    end

    AUD[(audit/audit.db\nappend-only • hash-chained)]

    G --> EX --> GATE
    EH --> COMP
    H --> EH
    GATE -->|approved| EG --> NEO
    FCAT --> COMP
    FA --> COMP
    FBY --> COMP
    NEO --> COMP --> FMT --> FIG
    COMP --> REC
    AK --> REC
    FB --> REC
    COMP --> NAR --> FW --> REP
    FIG --> EVAL
    REC --> EVAL
    COMP -.logs.-> AUD
    GATE -.logs.-> AUD
    NEO -.logs.-> AUD
    REC -.logs.-> AUD
    FW -.logs.-> AUD
```

## How each constraint maps to a component

| Constraint | Where it lives | Mechanism |
|---|---|---|
| 1 — reproducible | `src/util.py`, `src/engine/` | `Decimal` everywhere, fixed rounding policy, sorted iteration, frozen ingestion timestamps, `sort_keys` JSON. Re-runs are byte-identical. |
| 2 — traceable through graph | `src/graph/`, `src/engine/compute.py` | Figure inputs are obtained by graph traversal; each figure emits `graph_path` + `citation`; untraceable → `status: ERROR`. |
| 3 — no LLM numbers | `src/engine/` vs `src/narrative/` | Hard module boundary + firewall that rejects any narrative number not in the computed set. |
| 4 — reproduce Firm A | `src/reconcile/` | Per-figure diff vs `firm_A_answer_key.xlsx`. |
| 5 — reconfigure to Firm B | `config/*.yaml`, `src/config/loader.py` | Firm method is config-selected; engine implements all strategies; no code edit to switch. |
| append-only audit | `src/audit/log.py` | SQLite with `BEFORE UPDATE/DELETE → RAISE(ABORT)` triggers + SHA-256 hash chain. |

## Data flow for one figure (worked example: `aggregate_non_ig_exposure`)

```
config/firm_B.yaml: non_ig_membership = rating_incl_fallen_angels
        │
        ▼
engine/compute.py:_h_aggregate_non_ig
        │  traverses graph:
        │    (AssetClass:high_yield)-[:CONTRIBUTES_TO]->(Aggregate:non_ig)
        │    (AssetClass:structured_credit)-[:CONTRIBUTES_TO]->(Aggregate:non_ig)
        │    (Aggregate:non_ig)-[:HAS_LIMIT]->(Limit{max:20})
        │  + Firm-B rule: positions with credit_rating < BBB- join (Marina Bay BB)
        ▼
value = (HY 9M + SC 6M + Marina Bay 6M) / 100M = 21.0%   →  status BREACH (>20%)
citation = guidelines p.2 chunk_2b71 "aggregate non-IG cap"
```

The same handler under `firm_A.yaml` (`non_ig_membership = asset_class`) omits the
fallen-angel branch and yields `15.0% — OK`. **Same code, different config.**

## Backends

The graph layer has two interchangeable backends behind one interface
(`src/graph/client.py`):
- **Neo4j** — the docker-compose default; real Cypher traversals.
- **Embedded** — pure-Python over the same nodes/edges; lets the system run with
  `pip install` only and lets tests run with no external service.

Both return identical view structures, so figures and graph paths are
backend-independent.
