"""Narrative commentary layer (the ONLY place the LLM is used).

The LLM is given the already-computed figures and asked to write prose. It is
structurally incapable of being the source of a number because:
  * it receives figures as read-only input and produces TEXT, not values;
  * its output is passed through the firewall (firewall.py), which rejects any
    number not already in the computed figures.

If DEEPSEEK_API_KEY is unset, a deterministic mock narrative is produced from
the figures (still firewall-checked). Numbers never depend on the LLM either way.
"""
from __future__ import annotations

import os
from typing import Any

SYSTEM = (
    "You are a compliance report writer. You are given a fund's already-computed "
    "compliance figures as JSON. Write a short narrative (max 150 words) "
    "summarising the portfolio's compliance posture. CRITICAL: you may ONLY use "
    "numbers that appear verbatim in the provided figures. Do not compute, round, "
    "infer, or introduce any new number. Refer to breaches by name and status."
)


def _mock_narrative(firm: str, figures: list[dict]) -> str:
    # NB: deliberately introduces NO number of its own (not even counts) — every
    # numeric token below is copied verbatim from a computed figure, so the
    # firewall passes cleanly. Breach/at-limit counts are stated in words.
    breaches = [f for f in figures if f.get("status") == "BREACH"]
    at_limit = [f for f in figures if f.get("status") == "AT LIMIT"]
    _w = {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    lines = [
        f"Firm {firm} compliance summary.",
        f"The portfolio shows {_w.get(len(breaches), 'several')} limit breach(es) "
        f"and {_w.get(len(at_limit), 'several')} position(s) at limit.",
    ]
    for b in breaches:
        lines.append(
            f"BREACH: {b['metric']} at {b['value']} against limit {b['limit']} "
            f"(utilization {b['utilization']})."
        )
    for a in at_limit:
        lines.append(
            f"AT LIMIT: {a['metric']} at {a['value']} (limit {a['limit']})."
        )
    lines.append("All figures are produced by the deterministic engine and traced "
                 "to source via the knowledge graph.")
    return " ".join(lines)


def generate(firm: str, figures: list[dict]) -> dict[str, Any]:
    """Return {text, source}. source ∈ {deepseek, mock}."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {"text": _mock_narrative(firm, figures), "source": "mock"}
    try:
        import json

        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        slim = [
            {k: f.get(k) for k in ("metric", "value", "limit", "utilization", "status")}
            for f in figures
        ]
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps({"firm": firm, "figures": slim})},
            ],
            temperature=0,
        )
        return {"text": resp.choices[0].message.content.strip(), "source": "deepseek"}
    except Exception as exc:  # network/key failure must never break the report
        return {"text": _mock_narrative(firm, figures),
                "source": f"mock (deepseek unavailable: {exc})"}
