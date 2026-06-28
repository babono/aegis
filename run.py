#!/usr/bin/env python3
"""InterOpera take-home — single entrypoint.

Usage:
  python run.py --firm A                 # full pipeline -> Firm A report
  python run.py --firm B                 # full pipeline -> Firm B report (config only)
  python run.py --evaluate               # Phase 5: reconcile + traceability + firewall
  python run.py --multihop-demo          # Phase 2: multi-hop graph query demo
  python run.py --re-extract             # re-run LLM extraction -> review gate (needs key)

The same command produces both firms with NO code edit between runs — only the
--firm flag, which selects config/firm_<X>.yaml. Figures are computed by the
deterministic engine traversing the Neo4j graph; the LLM only writes narrative,
behind the firewall.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from src.util import canonical_json, sha256
from src.audit.log import AuditLog
from src.config.loader import load_config
from src.ingest.extract_holdings import load_positions
from src.review.gate import review_extraction
from src.graph.client import make_client
from src.graph.queries import breach_action_for_metric
from src.engine.compute import compute_all
from src.narrative import generate as narrative_gen
from src.narrative import firewall
from src.reconcile.reconciler import build_expected, reconcile
from src.report.writer import write_report

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(ROOT, "config")
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "sample_docs")
OUT_DIR = os.path.join(ROOT, "output")
AUDIT_DB = os.path.join(ROOT, "audit", "audit.db")

# Frozen run clock so even the audit log is replayable. Override with RUN_TS.
RUN_CLOCK = os.environ.get("RUN_TS", "2024-01-15T10:00:00Z")


def _load_extracted_graph() -> dict:
    with open(os.path.join(DATA_DIR, "extracted_graph.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _connect(backend: str, audit: AuditLog, run_id: str):
    """Return a graph client, auto-falling-back to embedded if Neo4j is absent."""
    uri = os.environ.get("NEO4J_URI", "")
    if backend == "auto":
        backend = "neo4j" if uri else "embedded"
    if backend == "neo4j":
        try:
            return make_client(
                "neo4j", uri=uri,
                user=os.environ.get("NEO4J_USER", "neo4j"),
                password=os.environ.get("NEO4J_PASSWORD", "testpassword"))
        except Exception as exc:
            print(f"[warn] Neo4j unavailable ({exc}); using embedded graph backend.")
            return make_client("embedded")
    return make_client("embedded")


def run_firm(firm: str, backend: str) -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    audit = AuditLog(AUDIT_DB)
    cfg = load_config(firm, CONFIG_DIR)
    run_id = "run_" + firm + "_" + sha256(canonical_json(cfg["methods"]))[:8]

    # 1. Configuration loaded (the firm-method switch).
    audit.record(ts=RUN_CLOCK, run_id=run_id, firm=firm, event="CONFIG_CHANGE",
                 trigger=f"--firm {firm}",
                 data={"name": cfg["name"], "methods": cfg["methods"],
                       "files": cfg["config_files"]}, retention="7y")

    # 2. Ingest + human review gate on the extracted graph.
    graph = _load_extracted_graph()
    positions = load_positions(os.path.join(DOCS_DIR, "sample_holdings.csv"))
    gate = review_extraction(graph)
    audit.record(ts=RUN_CLOCK, run_id=run_id, firm=firm, event="GRAPH_REVIEW_GATE",
                 trigger="extraction ingested", data=gate, retention="10y")
    if gate["decision"] != "AUTO_PASS":
        audit.record(ts=RUN_CLOCK, run_id=run_id, firm=firm, event="RUN_ABORTED",
                     trigger="gate held for human review", data=gate, retention="10y")
        print(f"[gate] extraction held for HUMAN_REVIEW: {gate['reasons']}")
        audit.close()
        sys.exit(2)

    # 3. Build the knowledge graph.
    client = _connect(backend, audit, run_id)
    stats = client.load(graph, positions)
    graph_hash = sha256(canonical_json({"nodes": graph["nodes"], "edges": graph["edges"],
                                         "positions": positions}))
    audit.record(ts=RUN_CLOCK, run_id=run_id, firm=firm, event="GRAPH_CONSTRUCTED",
                 trigger="ingestion approved",
                 data={"backend": client.backend, **stats, "graph_hash": graph_hash},
                 retention="7y")

    # 4. Compute figures by traversing the graph (deterministic; no LLM).
    chunks = {c["chunk_id"]: c for c in graph["chunks"]}
    figures = compute_all(client, cfg, chunks)
    for f in figures:
        audit.record(ts=RUN_CLOCK, run_id=run_id, firm=firm, event="FIGURE_COMPUTED",
                     trigger="report generation",
                     data={k: f.get(k) for k in
                           ("figure", "value", "status", "limit", "utilization",
                            "graph_path", "citation", "error")}, retention="7y")

    # 5. Narrative (LLM) + firewall verification of constraint 3.
    nar = narrative_gen.generate(firm, figures)
    fw = firewall.check(nar["text"], figures)
    if not fw["passed"]:
        # Reject narrative that introduces a number; fall back to safe mock.
        nar = {"text": narrative_gen._mock_narrative(firm, figures),
               "source": "mock (firewall rejected LLM narrative)"}
        fw_after = firewall.check(nar["text"], figures)
        fw = {"llm_rejected": True, "rejected_violations": fw["violations"], **fw_after}
    audit.record(ts=RUN_CLOCK, run_id=run_id, firm=firm, event="FIREWALL_CHECK",
                 trigger="narrative generated",
                 data={"source": nar["source"], **fw}, retention="7y")

    # 6. Reconcile against the firm's answer key.
    expected = build_expected(
        firm,
        os.path.join(DOCS_DIR, "firm_A_answer_key.xlsx"),
        os.path.join(DATA_DIR, "firm_B_expected_overrides.json"))
    recon = reconcile(figures, expected)
    audit.record(ts=RUN_CLOCK, run_id=run_id, firm=firm, event="RECONCILIATION",
                 trigger="figures computed",
                 data={"passed": recon["passed"], "failed": recon["failed"],
                       "all_passed": recon["all_passed"]}, retention="7y")

    # 7. Export report + machine-readable figures bundle.
    report_path = os.path.join(OUT_DIR, f"report_firm_{firm}.xlsx")
    write_report(os.path.join(DOCS_DIR, "report_template.xlsx"),
                 report_path, figures, nar["text"])
    bundle = {"firm": firm, "config": cfg["name"], "methods": cfg["methods"],
              "graph_backend": client.backend, "figures": figures,
              "narrative": nar, "firewall": fw, "reconciliation": recon}
    figures_path = os.path.join(OUT_DIR, f"figures_firm_{firm}.json")
    with open(figures_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(bundle, indent=2, sort_keys=True))
    audit.record(ts=RUN_CLOCK, run_id=run_id, firm=firm, event="REPORT_EXPORTED",
                 trigger="reconciliation complete",
                 data={"report": os.path.relpath(report_path, ROOT),
                       "figures": os.path.relpath(figures_path, ROOT)}, retention="10y")

    chain_ok = audit.verify_chain()
    client.close()
    audit.close()

    _print_firm_summary(firm, cfg, figures, recon, fw, nar, chain_ok)
    return bundle


def _print_firm_summary(firm, cfg, figures, recon, fw, nar, chain_ok):
    print(f"\n{'='*78}\nFIRM {firm} — {cfg['name']}")
    print(f"methods: {cfg['methods']}")
    print(f"{'-'*78}")
    print(f"{'Metric':40} {'Value':>10} {'Util':>10} {'Status':>9}")
    for f in figures:
        if f.get("status") == "ERROR":
            print(f"{f['metric']:40} {'ERROR':>10} {'':>10} {'ERROR':>9}")
        else:
            print(f"{f['metric']:40} {f['value']:>10} {f['utilization']:>10} {f['status']:>9}")
    print(f"{'-'*78}")
    print(f"reconciliation: {recon['passed']}/{recon['total']} pass "
          f"(all_passed={recon['all_passed']})")
    print(f"firewall: passed={fw['passed']} | narrative source={nar['source']}")
    print(f"audit chain intact: {chain_ok}")


def evaluate() -> None:
    """Phase 5 — combined reconciliation + traceability + firewall report."""
    summary = {"firms": {}}
    for firm in ("A", "B"):
        path = os.path.join(OUT_DIR, f"figures_firm_{firm}.json")
        if not os.path.exists(path):
            print(f"[evaluate] missing {path}; run --firm {firm} first.")
            continue
        with open(path, encoding="utf-8") as fh:
            bundle = json.load(fh)
        figures = bundle["figures"]
        # Traceability: every non-error figure must resolve figure->path->source.
        trace = []
        for f in figures:
            if f.get("status") == "ERROR":
                trace.append({"figure": f["figure"], "traceable": False,
                              "reason": f.get("error")})
                continue
            c = f.get("citation") or {}
            ok = bool(f.get("graph_path")) and all(
                c.get(k) for k in ("source_doc", "page", "chunk_id", "passage_summary"))
            trace.append({"figure": f["figure"], "traceable": ok})
        summary["firms"][firm] = {
            "reconciliation": bundle["reconciliation"],
            "firewall": bundle["firewall"],
            "traceability": {"all_traceable": all(t["traceable"] for t in trace),
                             "rows": trace},
        }

    with open(os.path.join(OUT_DIR, "evaluation.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, indent=2, sort_keys=True))

    print(f"\n{'='*78}\nPHASE 5 — EVALUATION")
    for firm, s in summary["firms"].items():
        r, fw, tr = s["reconciliation"], s["firewall"], s["traceability"]
        print(f"\nFirm {firm}:")
        print(f"  reconciliation : {r['passed']}/{r['total']} pass "
              f"(all_passed={r['all_passed']})")
        print(f"  traceability   : all_traceable={tr['all_traceable']}")
        print(f"  firewall       : passed={fw['passed']} "
              f"(no LLM-introduced numbers)")
        for row in r["rows"]:
            if row["result"] not in ("PASS",):
                print(f"    [{row['result']}] {row['metric']}: {row.get('checks', row)}")
    print(f"\nWrote {os.path.join('output', 'evaluation.json')}")


def multihop_demo(backend: str) -> None:
    audit = AuditLog(AUDIT_DB)
    graph = _load_extracted_graph()
    positions = load_positions(os.path.join(DOCS_DIR, "sample_holdings.csv"))
    client = _connect(backend, audit, "demo")
    client.load(graph, positions)
    print("\nMulti-hop query: 'breach action if portfolio duration exceeds its "
          "limit, and who is notified?'")
    print(json.dumps(breach_action_for_metric(client, "modified_duration"), indent=2))
    client.close()
    audit.close()


def re_extract() -> None:
    from src.ingest.extract_guidelines import reextract
    candidate = reextract(os.path.join(DOCS_DIR, "sample_fund_guidelines.pdf"))
    gate = review_extraction(candidate)
    out = os.path.join(DATA_DIR, "extracted_graph.candidate.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(candidate, indent=2, sort_keys=True))
    print(f"Candidate written to {out}\nGate decision: {gate['decision']} ({gate['reasons']})")
    print("Candidate is NOT trusted until a human approves it and promotes it to "
          "data/extracted_graph.json.")


def main() -> None:
    ap = argparse.ArgumentParser(description="InterOpera take-home pipeline")
    ap.add_argument("--firm", choices=["A", "B"])
    ap.add_argument("--evaluate", action="store_true")
    ap.add_argument("--multihop-demo", action="store_true")
    ap.add_argument("--re-extract", action="store_true")
    ap.add_argument("--reconcile-report", action="store_true",
                    help="alias for --evaluate")
    ap.add_argument("--graph-backend", default="auto",
                    choices=["auto", "neo4j", "embedded"])
    args = ap.parse_args()

    if args.re_extract:
        re_extract()
    elif args.multihop_demo:
        multihop_demo(args.graph_backend)
    elif args.evaluate or args.reconcile_report:
        evaluate()
    elif args.firm:
        run_firm(args.firm, args.graph_backend)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
