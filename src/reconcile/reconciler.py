"""Reconcile computed figures against a firm's answer key (Phase 4/5).

Firm A's expected figures come from firm_A_answer_key.xlsx. Firm B's answer key
is Firm A's with the rows that differ overridden per firm_B_brief.md (the brief
states those explicitly). We compare the substantive columns Value / Limit /
Status. Utilization is representational (percent for A, truncated bps for B) and
is therefore reported separately, not diffed across formats.
"""
from __future__ import annotations

import json
import os
import re
from decimal import Decimal
from typing import Any, Optional

import openpyxl


def _norm(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _leading_number(s: str) -> Optional[Decimal]:
    m = re.search(r"-?\d[\d,]*\.?\d*", s.replace(",", ""))
    return Decimal(m.group()) if m else None


def load_answer_key(xlsx_path: str) -> dict[str, dict]:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header = [_norm(c) for c in rows[0]]
    idx = {name: i for i, name in enumerate(header)}
    out: dict[str, dict] = {}
    for r in rows[1:]:
        metric = _norm(r[idx["Metric"]])
        if not metric:
            continue
        out[metric] = {
            "Section": _norm(r[idx["Section"]]),
            "Value": _norm(r[idx["Value"]]),
            "Limit": _norm(r[idx["Limit"]]),
            "Utilization": _norm(r[idx["Utilization"]]),
            "Status": _norm(r[idx["Status"]]),
        }
    return out


def build_expected(firm: str, answer_key_path: str, overrides_path: str) -> dict[str, dict]:
    expected = load_answer_key(answer_key_path)
    if firm.upper() == "B":
        with open(overrides_path, encoding="utf-8") as fh:
            overrides = json.load(fh)["overrides"]
        for metric, fields in overrides.items():
            expected.setdefault(metric, {}).update(fields)
    return expected


def reconcile(figures: list[dict], expected: dict[str, dict]) -> dict[str, Any]:
    results = []
    passed = 0
    for fig in figures:
        metric = fig["metric"]
        exp = expected.get(metric)
        if fig.get("status") == "ERROR":
            results.append({"metric": metric, "result": "ERROR",
                            "detail": fig.get("error")})
            continue
        if exp is None:
            results.append({"metric": metric, "result": "NO_KEY"})
            continue

        checks = {}
        # Value (with numeric delta when both parse as numbers).
        got_v, exp_v = _norm(fig["value"]), _norm(exp["Value"])
        gv, ev = _leading_number(got_v), _leading_number(exp_v)
        delta = (gv - ev) if (gv is not None and ev is not None) else None
        checks["value"] = {"got": got_v, "expected": exp_v,
                           "match": got_v == exp_v,
                           "delta": (str(delta) if delta is not None else None)}
        checks["status"] = {"got": fig["status"], "expected": exp["Status"],
                            "match": fig["status"] == exp["Status"]}
        checks["limit"] = {"got": _norm(fig["limit"]), "expected": _norm(exp["Limit"]),
                           "match": _norm(fig["limit"]) == _norm(exp["Limit"])}

        ok = all(c["match"] for c in checks.values())
        passed += 1 if ok else 0
        results.append({"metric": metric, "result": "PASS" if ok else "FAIL",
                        "checks": checks})

    return {
        "total": len(figures),
        "passed": passed,
        "failed": len(figures) - passed,
        "all_passed": passed == len(figures),
        "rows": results,
    }
