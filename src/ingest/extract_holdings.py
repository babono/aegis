"""Deterministic ingestion of the holdings snapshot.

The holdings CSV is structured data, so there is NO LLM in this path — it is a
plain, reproducible parse. Each row becomes a Position with provenance (the CSV
is the source document; the row number is the locator).
"""
from __future__ import annotations

import csv
from typing import Any

# Frozen so re-runs are byte-identical (constraint 1). Represents when this
# period-end snapshot was ingested.
HOLDINGS_INGESTED_AT = "2024-01-15T09:05:00Z"


def load_positions(csv_path: str) -> list[dict[str, Any]]:
    """Parse holdings into Position records, sorted by instrument_id."""
    positions: list[dict[str, Any]] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row_no, row in enumerate(csv.DictReader(fh), start=2):  # row 1 = header
            positions.append(
                {
                    "instrument_id": row["instrument_id"].strip(),
                    "instrument_name": row["instrument_name"].strip(),
                    "asset_class": row["asset_class"].strip(),
                    "issuer_name": row["issuer_name"].strip(),
                    "issuer_type": row["issuer_type"].strip(),
                    "parent_issuer": row["parent_issuer"].strip() or None,
                    "credit_rating": row["credit_rating"].strip() or None,
                    "downgraded_from": row["downgraded_from"].strip() or None,
                    "market_value_sgd": row["market_value_sgd"].strip(),
                    "modified_duration": row["modified_duration"].strip(),
                    "provenance": {
                        "source_doc": "sample_holdings.csv",
                        "row": row_no,
                        "ingested_at": HOLDINGS_INGESTED_AT,
                        "extraction_confidence": 1.0,  # structured source, exact
                    },
                }
            )
    positions.sort(key=lambda p: p["instrument_id"])
    return positions
