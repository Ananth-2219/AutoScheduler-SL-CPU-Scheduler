"""Oracle-labeled dataset generation."""

from __future__ import annotations

import csv
from pathlib import Path

from autoscheduler.evaluation import compare_algorithms, oracle_label
from autoscheduler.features import extract_features
from autoscheduler.workloads import PROFILES, generate_workload


def build_dataset(samples_per_profile: int = 500, seed: int = 42) -> list[dict]:
    if samples_per_profile <= 0:
        raise ValueError("samples_per_profile must be positive")

    rows = []
    for profile_index, profile in enumerate(PROFILES):
        for sample_index in range(samples_per_profile):
            workload_seed = seed * 10_000_000 + profile_index * 1_000_000 + sample_index
            workload = generate_workload(profile, workload_seed)
            label, scores = oracle_label(compare_algorithms(workload.processes))
            row = extract_features(workload.processes)
            row.update({"profile": profile, "seed": workload_seed, "label": label})
            row.update({f"score_{name.lower().replace(' ', '_')}": score for name, score in scores.items()})
            rows.append(row)
    return rows


def save_dataset(rows: list[dict], path: str | Path) -> Path:
    if not rows:
        raise ValueError("dataset must not be empty")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    return path
