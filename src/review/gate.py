"""Human-in-the-loop gate for the extracted graph (Phase 1 requirement).

Entity/relationship extraction is error-prone, so the graph's contents must be
verified by a human before any report trusts them. This gate encodes the
*criterion* that decides auto-pass vs. human review, and records the decision.

Decision criterion (auto-pass vs. human review):
  * Every node and edge must carry an extraction_confidence >= MIN_CONFIDENCE.
  * The extraction must be explicitly approved (meta.extraction_method ==
    "llm_assisted_human_approved" and an approved_by signer is present).
A candidate failing either is routed to HUMAN_REVIEW and must not be ingested.

The committed data/extracted_graph.json is already approved, so normal runs
auto-pass. A freshly re-extracted candidate (status llm_candidate_unapproved)
is held for review — demonstrating the gate and an obvious failure mode.
"""
from __future__ import annotations

from typing import Any

MIN_CONFIDENCE = 0.75


def review_extraction(graph: dict[str, Any]) -> dict[str, Any]:
    """Return a gate decision: {decision, reasons, low_confidence_items}."""
    reasons: list[str] = []
    low_conf: list[dict[str, Any]] = []

    for node in graph.get("nodes", []):
        conf = node.get("provenance", {}).get("extraction_confidence", 0.0)
        if conf < MIN_CONFIDENCE:
            low_conf.append({"kind": "node", "id": node.get("id"), "confidence": conf})
    for edge in graph.get("edges", []):
        conf = edge.get("provenance", {}).get("extraction_confidence", 0.0)
        if conf < MIN_CONFIDENCE:
            low_conf.append(
                {"kind": "edge", "edge": f'{edge.get("from")}->{edge.get("to")}',
                 "confidence": conf}
            )

    method = graph.get("meta", {}).get("extraction_method")
    approved_by = graph.get("meta", {}).get("approved_by")

    if low_conf:
        reasons.append(f"{len(low_conf)} item(s) below confidence floor {MIN_CONFIDENCE}")
    if method != "llm_assisted_human_approved":
        reasons.append(f"extraction not human-approved (method={method!r})")
    if not approved_by:
        reasons.append("no approver recorded")

    decision = "AUTO_PASS" if not reasons else "HUMAN_REVIEW"
    return {
        "decision": decision,
        "reasons": reasons,
        "low_confidence_items": low_conf,
        "min_confidence": MIN_CONFIDENCE,
    }
