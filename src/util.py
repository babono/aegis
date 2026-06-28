"""Determinism helpers shared across the system (constraint 1).

Every number that reaches a report flows through Decimal arithmetic with an
explicit, fixed rounding policy. We never let binary float rounding or hash /
set iteration order influence a reported figure. JSON is always serialised with
sorted keys so two runs produce byte-identical artifacts.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from typing import Any

# Canonical rating scale, highest credit quality first. Used to decide whether a
# holding is below the investment-grade floor (the "fallen angel" rule).
RATING_SCALE = [
    "AAA",
    "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-",
    "B+", "B", "B-",
    "CCC+", "CCC", "CCC-",
    "CC", "C", "D",
]


def D(value: Any) -> Decimal:
    """Coerce to Decimal via str() so float artifacts never leak in."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def rating_rank(rating: str) -> int:
    """Position on the rating scale (0 = AAA). Higher = lower credit quality."""
    return RATING_SCALE.index(rating)


def is_below_investment_grade(rating: str, ig_floor: str) -> bool:
    """True if `rating` is strictly worse than the IG floor (e.g. BB+ vs BBB-)."""
    if not rating:
        return False
    return rating_rank(rating) > rating_rank(ig_floor)


def quantize(value: Decimal, decimals: int, truncate: bool = False) -> Decimal:
    """Round (or truncate) a Decimal to a fixed number of decimal places."""
    q = Decimal(1).scaleb(-decimals)  # e.g. decimals=1 -> Decimal('0.1')
    rounding = ROUND_DOWN if truncate else ROUND_HALF_UP
    return value.quantize(q, rounding=rounding)


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace drift, stable separators."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
