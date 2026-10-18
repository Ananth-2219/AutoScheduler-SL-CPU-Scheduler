"""Leakage-safe splits for observed real-trace feature rows."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


SPLIT_NAMES = ("train", "validation", "test")


def _group_key(row: dict[str, Any], group_by: tuple[str, ...]) -> tuple[str, ...]:
    values = []
    for field in group_by:
        value = row.get(field)
        if value is None or value == "":
            raise ValueError(f"feature row requires non-empty group field: {field}")
        values.append(str(value))
    return tuple(values)


def _group_counts(total: int, fractions: dict[str, float]) -> dict[str, int]:
    if total < len(SPLIT_NAMES):
        raise ValueError("grouped splitting requires at least three distinct groups")
    counts = {name: 1 for name in SPLIT_NAMES}
    targets = {name: total * fractions[name] for name in SPLIT_NAMES}
    for _ in range(total - len(SPLIT_NAMES)):
        name = max(SPLIT_NAMES, key=lambda candidate: (targets[candidate] - counts[candidate], -SPLIT_NAMES.index(candidate)))
        counts[name] += 1
    return counts


def split_feature_rows(
    rows: Iterable[dict[str, Any]], fractions: dict[str, float], group_by: tuple[str, ...], seed: int
) -> dict[str, list[dict[str, Any]]]:
    """Split rows by complete metadata groups; no group may span a split."""
    if set(fractions) != set(SPLIT_NAMES) or abs(sum(fractions.values()) - 1.0) > 1e-9:
        raise ValueError("split fractions must contain train, validation, and test and sum to 1")
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_group_key(row, group_by)].append(row)
    keys = sorted(grouped)
    random.Random(seed).shuffle(keys)
    counts = _group_counts(len(keys), fractions)
    boundaries = (counts["train"], counts["train"] + counts["validation"])
    split_keys = {
        "train": keys[:boundaries[0]],
        "validation": keys[boundaries[0]:boundaries[1]],
        "test": keys[boundaries[1]:],
    }
    return {
        name: [row for key in split_keys[name] for row in grouped[key]]
        for name in SPLIT_NAMES
    }


def write_split_manifest(
    rows: Iterable[dict[str, Any]], output: str | Path, fractions: dict[str, float],
    group_by: tuple[str, ...], seed: int,
) -> dict[str, Any]:
    splits = split_feature_rows(rows, fractions, group_by, seed)
    manifest = {
        "group_by": list(group_by),
        "seed": seed,
        "fractions": fractions,
        "row_counts": {name: len(split) for name, split in splits.items()},
        "trace_ids": {name: sorted({row["trace_id"] for row in split}) for name, split in splits.items()},
        "group_counts": {name: len({_group_key(row, group_by) for row in split}) for name, split in splits.items()},
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def read_feature_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))
