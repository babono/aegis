# Notes, trade-offs & what I'd improve

A candid engineering reflection on this submission — the decisions I made, what I
deliberately left out, and where I'd go deeper with more time.

## Process & AI assistance

I built this with the help of an AI coding assistant, which I used to scaffold
the project and accelerate the boilerplate (the graph client, the formatting
layer, the Next.js/FastAPI web product). I directed the architecture around the
five hard constraints and treated the assistant as a pair-programmer, not an
oracle: I verified every reported figure against the answer key both by hand and
through the test suite, and I focused my own understanding on the two parts that
*are* the assignment — the graph-traversal computation path
(`src/engine/compute.py`) and the "no-LLM-numbers" firewall
(`src/narrative/firewall.py`).

I'm noting this because I'd rather be transparent about how I work than present
the polish as something it isn't. The parts I can defend line-by-line are the
compute/traceability/firewall logic and the firm-switch design; the areas I'd
still like to deepen are listed at the bottom.

## Key design decisions (and why)

- **Knowledge graph as the single source of truth.** Every figure's inputs are
  pulled from graph nodes that carry their own provenance, so the
  `figure → graph path → source` chain is genuine rather than decorative. This
  is the spine of constraint 2.
- **A deterministic engine, with the LLM strictly downstream.** Numbers come
  only from `src/engine`; the LLM writes narrative and is validated by a
  firewall. This makes constraint 3 a structural property, not a promise.
- **Firm method as configuration, not code.** The three ways Firm B differs are
  three keys in a YAML file; the engine implements both branches of each. This
  is what lets Firm B reproduce without an engine edit (constraint 5).
- **Two graph backends behind one interface.** Neo4j for the "real Cypher" story
  in local Docker, and a pure-Python embedded backend so the system also runs
  with no container and deploys cheaply (no database to host). Both return
  identical results, so figures are backend-independent.
- **Exact reconciliation (zero tolerance).** Because NAV is a round SGD 100M and
  every figure is hand-derivable, there's no rounding ambiguity to absorb — so I
  reconcile Value/Limit/Status exactly rather than within a tolerance.

## Known limitations (deliberate, given the one-week scope)

- **Guidelines extraction is AI-assisted then frozen.** The committed
  `data/extracted_graph.json` is a human-approved snapshot. Re-extraction exists
  (`--re-extract`) and is gated, but I did not build a full extraction-QA loop.
- **Error handling covers the happy path + two failure modes** (a low-confidence
  extraction held at the gate; an untraceable figure returned as `ERROR`), as the
  brief allows — not exhaustive exception handling.
- **No production auth/secrets management.** The audit DB is local SQLite; secrets
  are read from environment variables.
- **Rating model is intentionally small.** A fixed rating scale covers the sample;
  a real system would handle agency-specific scales and split ratings.
- **The hosted demo uses the embedded backend**, so the live site doesn't exercise
  Neo4j (the local Docker run does).

## What I'd add for production

- A managed graph database and a proper extraction pipeline with reviewer tooling
  and versioned approvals.
- The audit log in an append-only store with stronger guarantees than a SQLite
  trigger (e.g. object-lock storage or a ledger DB), plus signed report exports.
- AuthN/Z, secrets in a vault, and per-tenant isolation if multiple funds/firms
  run concurrently.
- Broader instrument coverage (cross-currency, derivatives, split ratings) and a
  fuller risk model (real VaR/ES rather than the duration/DV01 subset reported).

## What I'd like to deepen (honest learning goals)

- Graph data modelling and Cypher at scale — I understand the traversals here,
  but want more depth on indexing and query performance on large graphs.
- Production-grade audit/ledger patterns beyond the trigger + hash-chain approach.
- Retrieval/grounding techniques for the narrative layer (the brief lists
  global/local retrieval as a bonus I didn't implement).
