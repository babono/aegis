"""Multi-hop query demonstrations (Phase 2 requirement).

Shows the graph answering questions by TRAVERSAL rather than re-reading the
document — e.g. "what is the breach action if portfolio duration exceeds its
limit, and who is notified?" walks
    (RiskMetric)-[:HAS_BREACH_ACTION]->(BreachAction)-[:OWNED_BY]->(Owner)
"""
from __future__ import annotations

from typing import Any


def breach_action_for_metric(client, metric_name: str) -> dict[str, Any]:
    rm = client.risk_metric_view(metric_name)
    return {
        "metric": rm["label"] or metric_name,
        "threshold": rm["threshold"],
        "breach_action": (rm["breach_action"] or {}).get("action"),
        "notified": (rm["owner"] or {}).get("name"),
        "graph_path": (
            f"(RiskMetric:{metric_name})-[:HAS_BREACH_ACTION]->"
            f"(BreachAction)-[:OWNED_BY]->(Owner)"
        ),
        "citation": rm["provenance"],
    }
