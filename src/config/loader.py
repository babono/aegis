"""Load the firm method config + shared figure catalogue.

Switching firms = pointing at a different firm_*.yaml. The engine code is
firm-agnostic; it implements every strategy and the config only SELECTS one
(constraint 5). We validate the selected method values up front so a typo fails
loudly rather than silently producing Firm A's numbers under Firm B's name.
"""
from __future__ import annotations

import os
from typing import Any

import yaml

VALID_METHODS = {
    "non_ig_membership": {"asset_class", "rating_incl_fallen_angels"},
    "gre_grouping": {"issuer", "parent_issuer"},
    "utilization_format": {"percent_1dp", "truncated_bps"},
}


def load_config(firm: str, config_dir: str) -> dict[str, Any]:
    firm_path = os.path.join(config_dir, f"firm_{firm}.yaml")
    figures_path = os.path.join(config_dir, "figures.yaml")
    with open(firm_path, encoding="utf-8") as fh:
        firm_cfg = yaml.safe_load(fh)
    with open(figures_path, encoding="utf-8") as fh:
        figures = yaml.safe_load(fh)["figures"]

    methods = firm_cfg["methods"]
    for key, allowed in VALID_METHODS.items():
        if methods.get(key) not in allowed:
            raise ValueError(
                f"firm_{firm}.yaml: methods.{key}={methods.get(key)!r} invalid; "
                f"expected one of {sorted(allowed)}"
            )
    return {
        "firm": firm_cfg["firm"],
        "name": firm_cfg["name"],
        "methods": methods,
        "rounding": firm_cfg.get("rounding", {}),
        "figures": figures,
        "config_files": {"firm": firm_path, "figures": figures_path},
    }
