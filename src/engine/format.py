"""Deterministic formatting of computed values, limits, utilization and status.

Every formatter takes already-computed Decimals and renders strings. No value is
ever *produced* here — only rendered — and the rendering is a pure function of
(Decimal, firm rounding/format config), so it is byte-reproducible.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from src.util import D, quantize


# --------------------------------------------------------------------------- #
# Value rendering                                                             #
# --------------------------------------------------------------------------- #
def render_value(value: Decimal, style: str, rounding: dict) -> str:
    if style == "pct1":
        return f"{quantize(value, rounding.get('value_decimals', 1))}%"
    if style == "yrs2":
        return f"{quantize(value, rounding.get('duration_decimals', 2))} yrs"
    if style == "sgd_per_bp":
        return f"SGD {int(quantize(value, 0)):,} / bp"
    raise ValueError(f"unknown value_style: {style}")


# --------------------------------------------------------------------------- #
# Limit rendering (numbers come from the graph; style from the figure config) #
# --------------------------------------------------------------------------- #
def render_limit(limit: dict, style: str) -> str:
    lo, hi = limit.get("min"), limit.get("max")
    if style == "range_pct":
        return f"{_g(lo)}–{_g(hi)}%"
    if style == "min_pct":
        return f"min {_g(lo)}%"
    if style == "max_pct":
        return f"max {_g(hi)}%"
    if style == "range_yrs":
        return f"{lo}–{hi} yrs"
    if style == "max_amount":
        return f"max {int(hi):,}"
    raise ValueError(f"unknown limit_style: {style}")


def _g(x) -> str:
    """Render a bound like 20 or 0 without a trailing .0."""
    if x is None:
        return ""
    d = D(x)
    return str(d.to_integral_value()) if d == d.to_integral_value() else str(d)


# --------------------------------------------------------------------------- #
# Utilization rendering (firm-configurable: percent vs truncated bps)         #
# --------------------------------------------------------------------------- #
def render_utilization(value: Decimal, bound: Optional[Decimal], basis: str,
                       fmt: str, rounding: dict) -> str:
    if basis == "none" or bound is None or bound == 0:
        return "n/a"
    ratio = value / bound  # pure fraction, e.g. 35/60
    if fmt == "truncated_bps":
        bps = quantize(ratio * Decimal(10000), 0, truncate=True)
        return f"{int(bps)} bps"
    # default percent_1dp
    pct = quantize(ratio * Decimal(100), rounding.get("utilization_decimals", 1))
    return f"{pct}%"


# --------------------------------------------------------------------------- #
# Status (pure comparison of value against the graph's bounds)                #
# --------------------------------------------------------------------------- #
def compute_status(value: Decimal, limit: dict) -> str:
    lo = limit.get("min")
    hi = limit.get("max")
    lo = D(lo) if lo is not None else None
    hi = D(hi) if hi is not None else None
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        return "BREACH"
    if (lo is not None and value == lo) or (hi is not None and value == hi):
        return "AT LIMIT"
    return "OK"
