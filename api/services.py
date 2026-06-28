"""Service layer for the web API.

These functions are thin adapters over the SAME engine modules the CLI uses
(`src/`). They compute NOTHING new — they call `compute_all`, `reconcile`,
`firewall`, etc. and shape the results for HTTP. This is what keeps the web layer
faithful to the constraints: the browser can only ever see what the deterministic
engine produced.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from src.config.loader import load_config
from src.engine.compute import compute_all
from src.graph.client import make_client
from src.graph.queries import breach_action_for_metric
from src.ingest.extract_holdings import load_positions
from src.narrative import firewall
from src.narrative import generate as narrative_gen
from src.reconcile.reconciler import build_expected, reconcile
from src.audit.log import AuditLog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "sample_docs")
OUT_DIR = os.path.join(ROOT, "output")
AUDIT_DB = os.path.join(ROOT, "audit", "audit.db")

# The hosted API uses the in-process embedded graph backend: stateless per
# request, no shared DB contention, identical results to Neo4j (which stars in
# the local `docker compose up`). Override with API_GRAPH_BACKEND=neo4j.
BACKEND = os.environ.get("API_GRAPH_BACKEND", "embedded")

# Which firm method "knob" is responsible for each figure kind (for the trace
# panel's "produced by rule" line).
RULE_FOR_KIND = {
    "aggregate_non_ig": "non_ig_membership",
    "concentration_gre": "gre_grouping",
}


def list_firms() -> list[dict]:
    firms = []
    for f in ("A", "B"):
        cfg = load_config(f, CONFIG_DIR)
        firms.append({"firm": cfg["firm"], "name": cfg["name"],
                      "methods": cfg["methods"]})
    return firms


def _load_graph() -> dict:
    with open(os.path.join(DATA_DIR, "extracted_graph.json"), encoding="utf-8") as fh:
        return json.load(fh)


def compute_bundle(firm: str) -> dict[str, Any]:
    """Run the deterministic compute + reconcile + firewall for a firm and return
    a JSON-friendly bundle. No audit writes, no file export (that is /run)."""
    cfg = load_config(firm, CONFIG_DIR)
    graph = _load_graph()
    positions = load_positions(os.path.join(DOCS_DIR, "sample_holdings.csv"))
    client = make_client(BACKEND,
                         uri=os.environ.get("NEO4J_URI", ""),
                         user=os.environ.get("NEO4J_USER", "neo4j"),
                         password=os.environ.get("NEO4J_PASSWORD", "testpassword"))
    client.load(graph, positions)
    chunks = {c["chunk_id"]: c for c in graph["chunks"]}
    figures = compute_all(client, cfg, chunks)
    client.close()

    nar = narrative_gen.generate(firm, figures)
    fw = firewall.check(nar["text"], figures)
    if not fw["passed"]:
        nar = {"text": narrative_gen._mock_narrative(firm, figures),
               "source": "mock (firewall rejected LLM narrative)"}
        fw = {"llm_rejected": True, **firewall.check(nar["text"], figures)}

    expected = build_expected(
        firm, os.path.join(DOCS_DIR, "firm_A_answer_key.xlsx"),
        os.path.join(DATA_DIR, "firm_B_expected_overrides.json"))
    recon = reconcile(figures, expected)
    recon_by_metric = {r["metric"]: r for r in recon["rows"]}

    kind_by_id = {f["id"]: f["kind"] for f in cfg["figures"]}

    return {
        "firm": cfg["firm"],
        "name": cfg["name"],
        "methods": cfg["methods"],
        "graph_backend": BACKEND,
        "figures": figures,
        "narrative": nar,
        "firewall": fw,
        "reconciliation": recon,
        "_recon_by_metric": recon_by_metric,
        "_kind_by_id": kind_by_id,
    }


def get_figures(firm: str) -> dict[str, Any]:
    b = compute_bundle(firm)
    return {
        "firm": b["firm"], "name": b["name"], "methods": b["methods"],
        "graph_backend": b["graph_backend"],
        "summary": {
            "reconciliation": {k: b["reconciliation"][k]
                               for k in ("total", "passed", "failed", "all_passed")},
            "firewall_passed": b["firewall"]["passed"],
            "narrative_source": b["narrative"]["source"],
        },
        "figures": [_row(f, b) for f in b["figures"]],
        "narrative": b["narrative"]["text"],
    }


def _row(fig: dict, bundle: dict) -> dict:
    """A compact table row + just enough for the list view."""
    recon = bundle["_recon_by_metric"].get(fig["metric"], {})
    return {
        "figure": fig["figure"],
        "section": fig["section"],
        "metric": fig["metric"],
        "value": fig.get("value"),
        "limit": fig.get("limit"),
        "utilization": fig.get("utilization"),
        "status": fig.get("status"),
        "reconciled": recon.get("result"),
        "error": fig.get("error"),
    }


def get_figure_detail(firm: str, figure_id: str) -> Optional[dict]:
    b = compute_bundle(firm)
    fig = next((f for f in b["figures"] if f["figure"] == figure_id), None)
    if fig is None:
        return None
    recon = b["_recon_by_metric"].get(fig["metric"], {})
    kind = b["_kind_by_id"].get(figure_id)
    rule_key = RULE_FOR_KIND.get(kind)
    produced_by = {"utilization_format": b["methods"]["utilization_format"]}
    if rule_key:
        produced_by[rule_key] = b["methods"][rule_key]
    return {
        "firm": b["firm"],
        "figure": fig["figure"],
        "section": fig["section"],
        "metric": fig["metric"],
        "value": fig.get("value"),
        "status": fig.get("status"),
        "limit": fig.get("limit"),
        "utilization": fig.get("utilization"),
        "graph_path": fig.get("graph_path"),
        "citation": fig.get("citation"),
        "detail": fig.get("detail"),
        "error": fig.get("error"),
        "reconciliation": recon,        # PASS/FAIL + per-column delta vs answer key
        "produced_by_rule": produced_by,  # which config knob(s) drove this figure
    }


def get_reconciliation(firm: str) -> dict:
    b = compute_bundle(firm)
    return b["reconciliation"]


def multihop_demo() -> dict:
    graph = _load_graph()
    positions = load_positions(os.path.join(DOCS_DIR, "sample_holdings.csv"))
    client = make_client(BACKEND)
    client.load(graph, positions)
    res = breach_action_for_metric(client, "modified_duration")
    client.close()
    return res


def get_config(firm: str) -> dict:
    path = os.path.join(CONFIG_DIR, f"firm_{firm}.yaml")
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    cfg = load_config(firm, CONFIG_DIR)
    return {"firm": firm, "yaml": raw, "methods": cfg["methods"], "name": cfg["name"]}


def get_audit(limit: int = 500) -> dict:
    if not os.path.exists(AUDIT_DB):
        return {"chain_intact": None, "events": [],
                "note": "No audit log yet — POST /api/run to generate one."}
    log = AuditLog(AUDIT_DB)
    events = log.events()[-limit:]
    intact = log.verify_chain()
    log.close()
    for e in events:
        try:
            e["payload"] = json.loads(e["payload"])
        except Exception:
            pass
    return {"chain_intact": intact, "count": len(events), "events": events}


def run_full(firm: str) -> dict:
    """The audited pipeline: writes report + figures + audit log (mirrors the CLI).
    Returns a summary. Importing here avoids a module-level dependency cycle."""
    import run as cli  # the existing entrypoint module
    bundle = cli.run_firm(firm, os.environ.get("API_GRAPH_BACKEND", "auto"))
    return {
        "firm": bundle["firm"],
        "name": bundle["config"],
        "reconciliation": {k: bundle["reconciliation"][k]
                           for k in ("total", "passed", "failed", "all_passed")},
        "firewall_passed": bundle["firewall"]["passed"],
        "narrative_source": bundle["narrative"]["source"],
        "outputs": {
            "report": f"output/report_firm_{firm}.xlsx",
            "figures": f"output/figures_firm_{firm}.json",
        },
    }
