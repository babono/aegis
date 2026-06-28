"""The number firewall — verifies constraint 3 rather than asserting it.

The narrative layer may only restate numbers the engine already computed. This
module extracts every numeric token from the computed figures (the allowed set)
and from the narrative, and flags any number in the narrative that is NOT in the
allowed set. If the narrative introduces a number, the firewall fails and the
narrative is rejected — so an examiner can verify, mechanically, that no figure
originated in the LLM.
"""
from __future__ import annotations

import re
from typing import Any

# Matches integers/decimals with optional thousands separators: 35, 35.0, 85,000
_NUM = re.compile(r"\d[\d,]*\.?\d*")

# Numbers the narrative may use that are not "figures" — section references the
# guidelines themselves contain. Kept deliberately tiny and explicit.
STRUCTURAL_WHITELIST = {"2", "3", "4", "1"}  # e.g. "Section 3.2", "within 1h"


def _numbers(text: str) -> list[str]:
    return [m.group().replace(",", "").rstrip(".") for m in _NUM.finditer(text or "")]


def allowed_numbers(figures: list[dict]) -> set[str]:
    allowed: set[str] = set()
    for fig in figures:
        for field in ("value", "limit", "utilization"):
            for n in _numbers(str(fig.get(field, ""))):
                allowed.add(n)
        # numbers inside graph_path/detail are also engine-derived
        for n in _numbers(str(fig.get("detail", ""))):
            allowed.add(n)
    return allowed | STRUCTURAL_WHITELIST


def check(narrative: str, figures: list[dict]) -> dict[str, Any]:
    allowed = allowed_numbers(figures)
    violations = [n for n in _numbers(narrative) if n not in allowed]
    return {
        "passed": not violations,
        "violations": sorted(set(violations)),
        "allowed_count": len(allowed),
    }
