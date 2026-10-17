"""Frozen contract for the real Linux desktop ML experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_REAL_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "real_desktop_ml.json"


def validate_real_config(config: dict[str, Any]) -> None:
    required = {
        "schema_version", "experiment_id", "target", "data", "policies", "control",
        "features", "score_weights", "dataset", "models", "acceptance_gates", "seeds",
        "output_root",
    }
    missing = required - config.keys()
    if missing:
        raise ValueError(f"missing required config fields: {', '.join(sorted(missing))}")

    weights = config["score_weights"]
    if not weights or any(value < 0 for value in weights.values()) or abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("score weights must be non-negative and sum to 1")

    split = config["dataset"]["split"]
    if set(split) != {"train", "validation", "test"} or abs(sum(split.values()) - 1.0) > 1e-9:
        raise ValueError("dataset split fractions must contain train/validation/test and sum to 1")

    deployable = [policy["name"] for policy in config["policies"]["deployable"]]
    oracle_only = [policy["name"] for policy in config["policies"]["oracle_only"]]
    if not deployable or len(deployable) != len(set(deployable)):
        raise ValueError("deployable policy names must be non-empty and unique")
    overlap = set(deployable) & set(oracle_only)
    if overlap:
        raise ValueError(f"policies cannot be both deployable and oracle-only: {', '.join(sorted(overlap))}")

    control = config["control"]
    for field in ("initial_observation_ms", "feature_window_ms", "decision_interval_ms", "minimum_dwell_ms"):
        if control[field] <= 0:
            raise ValueError(f"{field} must be positive")
    if control["minimum_dwell_ms"] % control["decision_interval_ms"]:
        raise ValueError("minimum dwell must be a whole number of decision intervals")

    features = config["features"]
    if not features["allowed"] or set(features["allowed"]) & set(features["forbidden"]):
        raise ValueError("allowed and forbidden features must be non-empty and disjoint")

    families = config["models"]["families"]
    if not families or set(config["models"]["simplicity_order"]) != set(families):
        raise ValueError("model families and simplicity order must match")


def load_real_config(path: str | Path = DEFAULT_REAL_CONFIG) -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_real_config(config)
    return config


def config_hash(config: dict[str, Any]) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stamp_summary(summary: dict[str, Any], config: dict[str, Any], config_file: str | Path) -> dict[str, Any]:
    return {
        **summary,
        "experiment_config": {
            "file": Path(config_file).name,
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "sha256": config_hash(config),
        },
    }
