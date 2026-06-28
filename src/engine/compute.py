"""The deterministic computation engine (Phase 3 — the core).

Each report figure is computed by TRAVERSING the knowledge graph for its inputs
(positions, limits, memberships) and applying Decimal arithmetic. The language
model is NOWHERE in this path — these functions never import or call it. Every
figure emits {value, status, limit, utilization, graph_path, citation}. A figure
whose inputs cannot be traced through the graph is returned with status ERROR,
never a silently-emitted number (constraint 2).

Firm differences (constraint 5) enter ONLY as config-selected strategies:
  * non_ig_membership  : asset_class | rating_incl_fallen_angels
  * gre_grouping        : issuer | parent_issuer
  * utilization_format  : percent_1dp | truncated_bps
The engine implements all of them; the firm config picks one each.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from src.util import D, is_below_investment_grade
from src.engine.format import (
    compute_status,
    render_limit,
    render_utilization,
    render_value,
)


class TraceError(Exception):
    """Raised when a figure's inputs cannot be resolved through the graph."""


def compute_all(client, config: dict, chunks: dict[str, dict]) -> list[dict]:
    """Compute every figure in the catalogue, in catalogue order."""
    nav = client.total_nav()
    if nav == 0:
        raise TraceError("NAV is zero; cannot compute allocations")
    ctx = {"client": client, "config": config, "chunks": chunks, "nav": nav}
    results = []
    for fig in config["figures"]:
        results.append(_compute_one(fig, ctx))
    return results


def _compute_one(fig: dict, ctx: dict) -> dict:
    handler: Callable = _HANDLERS[fig["kind"]]
    try:
        raw = handler(fig, ctx)  # -> {value: Decimal, limit, graph_path, citation, extra}
    except (KeyError, TraceError) as exc:
        # Untraceable -> ERROR, not a silent number.
        return {
            "figure": fig["id"],
            "section": fig["section"],
            "metric": fig["metric"],
            "status": "ERROR",
            "error": f"untraceable: {exc}",
        }

    cfg = ctx["config"]
    rounding = cfg["rounding"]
    value = raw["value"]
    limit = raw["limit"]
    bound = _util_bound(limit, fig["util_basis"])
    out = {
        "figure": fig["id"],
        "section": fig["section"],
        "metric": fig["metric"],
        "value": render_value(value, fig["value_style"], rounding),
        "status": compute_status(value, limit),
        "limit": render_limit(limit, fig["limit_style"]),
        "utilization": render_utilization(
            value, bound, fig["util_basis"],
            cfg["methods"]["utilization_format"], rounding),
        "graph_path": raw["graph_path"],
        "citation": raw["citation"],
    }
    if "extra" in raw:
        out["detail"] = raw["extra"]
    return out


def _util_bound(limit: dict, basis: str):
    if basis == "max":
        return D(limit["max"]) if limit.get("max") is not None else None
    if basis == "min":
        return D(limit["min"]) if limit.get("min") is not None else None
    return None


def _citation(provenance: dict, chunks: dict[str, dict]) -> dict:
    chunk_id = provenance.get("chunk_id")
    chunk = chunks.get(chunk_id, {})
    return {
        "source_doc": provenance.get("source_doc"),
        "page": provenance.get("page"),
        "chunk_id": chunk_id,
        "passage_summary": chunk.get("passage_summary"),
    }


def _pct_of_nav(amount: Decimal, nav: Decimal) -> Decimal:
    return amount / nav * Decimal(100)


# --------------------------------------------------------------------------- #
# Figure handlers — each returns Decimal value + traceability                 #
# --------------------------------------------------------------------------- #
def _h_allocation(fig: dict, ctx: dict) -> dict:
    name = fig["binds"]["asset_class"]
    view = ctx["client"].asset_class_view(name)
    total = sum((D(p["market_value_sgd"]) for p in view["positions"]), Decimal(0))
    value = _pct_of_nav(total, ctx["nav"])
    return {
        "value": value,
        "limit": view["limit"],
        "graph_path": (
            f"(Position)-[:IN_ASSET_CLASS]->(AssetClass:{view['code']})"
            f"-[:HAS_LIMIT]->(Limit)"
        ),
        "citation": _citation(view["provenance"], ctx["chunks"]),
        "extra": {"market_value_sgd": str(total),
                  "instruments": sorted(p["instrument_id"] for p in view["positions"])},
    }


def _h_aggregate_non_ig(fig: dict, ctx: dict) -> dict:
    client, cfg = ctx["client"], ctx["config"]
    view = client.non_ig_view()
    membership = cfg["methods"]["non_ig_membership"]
    ig_floor = cfg["methods"].get("ig_floor_rating", "BBB-")

    member_classes = {c["name"] for c in view["contributing_classes"]}
    included: dict[str, Decimal] = {}  # instrument_id -> mv
    rule_for: dict[str, str] = {}

    # Always: positions in asset classes that CONTRIBUTE_TO the aggregate.
    for p in client.all_positions():
        if p["asset_class"] in member_classes:
            included[p["instrument_id"]] = D(p["market_value_sgd"])
            rule_for[p["instrument_id"]] = "asset_class"

    # Firm B convention #1: fallen angels join by current rating, any class.
    if membership == "rating_incl_fallen_angels":
        for p in client.all_positions():
            r = p.get("credit_rating")
            if r and is_below_investment_grade(r, ig_floor):
                if p["instrument_id"] not in included:
                    included[p["instrument_id"]] = D(p["market_value_sgd"])
                    rule_for[p["instrument_id"]] = "fallen_angel"

    total = sum(included.values(), Decimal(0))
    value = _pct_of_nav(total, ctx["nav"])

    codes = [c["code"] for c in view["contributing_classes"]]
    path = "<-[:CONTRIBUTES_TO]-".join(
        [f"(Aggregate:non_ig)"] + [f"(AssetClass:{c})" for c in codes]
    ) + "-[:HAS_LIMIT]->(Limit)"
    if membership == "rating_incl_fallen_angels":
        path = ("(Position{rating<IG})-[:COUNTS_TOWARD]->" + path)

    return {
        "value": value,
        "limit": view["limit"],
        "graph_path": path,
        "citation": _citation(view["provenance"], ctx["chunks"]),
        "extra": {
            "membership_rule": membership,
            "market_value_sgd": str(total),
            "members": [
                {"instrument": iid, "rule": rule_for[iid]}
                for iid in sorted(included)
            ],
        },
    }


def _h_concentration_corporate(fig: dict, ctx: dict) -> dict:
    client = ctx["client"]
    cap = client.cap_view("single_issuer")
    buckets = client.issuer_exposures("corporate", "issuer")
    if not buckets:
        raise TraceError("no corporate issuers found")
    top = buckets[0]
    value = _pct_of_nav(top["market_value"], ctx["nav"])
    return {
        "value": value,
        "limit": cap["limit"],
        "graph_path": (
            f"(Position)-[:ISSUED_BY]->(Issuer:{_slug(top['key'])}) "
            f"; (Cap:single_issuer)"
        ),
        "citation": _citation(cap["provenance"], ctx["chunks"]),
        "extra": {"issuer": top["key"], "instruments": top["instruments"],
                  "market_value_sgd": str(top["market_value"])},
    }


def _h_concentration_gre(fig: dict, ctx: dict) -> dict:
    client, cfg = ctx["client"], ctx["config"]
    cap = client.cap_view("gre")
    grouping = cfg["methods"]["gre_grouping"]
    buckets = client.issuer_exposures("GRE", grouping)
    if not buckets:
        raise TraceError("no GRE issuers found")
    top = buckets[0]
    value = _pct_of_nav(top["market_value"], ctx["nav"])
    if grouping == "parent_issuer":
        path = (f"(Position)-[:ISSUED_BY]->(Issuer)-[:ROLLS_UP_TO]->"
                f"(ParentIssuer:{_slug(top['key'])}) ; (Cap:gre)")
    else:
        path = f"(Position)-[:ISSUED_BY]->(Issuer:{_slug(top['key'])}) ; (Cap:gre)"
    return {
        "value": value,
        "limit": cap["limit"],
        "graph_path": path,
        "citation": _citation(cap["provenance"], ctx["chunks"]),
        "extra": {"grouping": grouping, "group": top["key"],
                  "instruments": top["instruments"],
                  "market_value_sgd": str(top["market_value"])},
    }


def _h_liquidity(fig: dict, ctx: dict) -> dict:
    client = ctx["client"]
    floor = client.floor_view("liquid_assets")
    members = floor["limit"].get("members", [])
    total = Decimal(0)
    for p in client.all_positions():
        if p["asset_class"] in members:
            total += D(p["market_value_sgd"])
    value = _pct_of_nav(total, ctx["nav"])
    member_codes = "|".join(sorted(members))
    return {
        "value": value,
        "limit": floor["limit"],
        "graph_path": f"(AssetClass:[{member_codes}])-[:MEMBER_OF]->(Floor:liquid_assets)",
        "citation": _citation(floor["provenance"], ctx["chunks"]),
        "extra": {"members": members, "market_value_sgd": str(total)},
    }


def _h_duration(fig: dict, ctx: dict) -> dict:
    client = ctx["client"]
    rm = client.risk_metric_view("modified_duration")
    weighted = Decimal(0)
    for p in client.all_positions():
        weighted += D(p["market_value_sgd"]) * D(p["modified_duration"])
    value = weighted / ctx["nav"]
    return {
        "value": value,
        "limit": rm["threshold"],
        "graph_path": (
            "(Position)-[:IN_ASSET_CLASS]->(AssetClass) ; "
            "(RiskMetric:modified_duration)-[:HAS_THRESHOLD]->(Threshold)"
        ),
        "citation": _citation(rm["provenance"], ctx["chunks"]),
        "extra": {"weighted_mv_duration": str(weighted)},
    }


def _h_dv01(fig: dict, ctx: dict) -> dict:
    client = ctx["client"]
    rm = client.risk_metric_view("dv01")
    weighted = Decimal(0)
    for p in client.all_positions():
        weighted += D(p["market_value_sgd"]) * D(p["modified_duration"])
    # DV01 ~= MV * modified_duration * 1bp (0.0001).
    value = weighted * Decimal("0.0001")
    return {
        "value": value,
        "limit": rm["threshold"],
        "graph_path": (
            "(Position) ; (RiskMetric:dv01)-[:HAS_THRESHOLD]->(Threshold)"
        ),
        "citation": _citation(rm["provenance"], ctx["chunks"]),
        "extra": {"weighted_mv_duration": str(weighted)},
    }


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


_HANDLERS: dict[str, Callable[[dict, dict], dict]] = {
    "allocation": _h_allocation,
    "aggregate_non_ig": _h_aggregate_non_ig,
    "concentration_corporate": _h_concentration_corporate,
    "concentration_gre": _h_concentration_gre,
    "liquidity": _h_liquidity,
    "duration": _h_duration,
    "dv01": _h_dv01,
}
