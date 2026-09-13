"""Validation-only tuning for the Priority Round Robin baseline."""

from __future__ import annotations

from collections import Counter
from statistics import mean

from autoscheduler.dataset import build_dataset
from autoscheduler.evaluation import compare_algorithms, score_results
from autoscheduler.workloads import generate_workload


PRIORITY_RR_GRID = tuple(
    {"quantum": quantum, "aging_interval": aging_interval, "context_switch_cost": 1}
    for quantum in (1, 2, 4)
    for aging_interval in (4, 8, 12)
)


def _validation_rows(rows: list[dict], random_state: int) -> list[dict]:
    from sklearn.model_selection import train_test_split

    labels = [row["label"] for row in rows]
    stratify = labels if min(Counter(labels).values()) >= 2 else None
    _, holdout = train_test_split(
        list(range(len(rows))), test_size=0.30, random_state=random_state, stratify=stratify
    )
    holdout_labels = [labels[index] for index in holdout]
    holdout_stratify = holdout_labels if min(Counter(holdout_labels).values()) >= 2 else None
    validation, _ = train_test_split(
        holdout, test_size=0.50, random_state=random_state, stratify=holdout_stratify
    )
    return [rows[index] for index in validation]


def tune_priority_rr(samples_per_profile: int = 500, seed: int = 42) -> dict:
    """Select a Priority-RR configuration using only the fixed validation split."""
    validation_rows = _validation_rows(build_dataset(samples_per_profile, seed), seed)
    candidates = []
    for config in PRIORITY_RR_GRID:
        priority_rr_scores = []
        sjf_scores = []
        priority_rr_max_wait = 0
        for row in validation_rows:
            processes = generate_workload(row["profile"], row["seed"]).processes
            results = compare_algorithms(processes, priority_rr_config=config)
            scores = score_results(results)
            priority_rr_scores.append(scores["Priority RR"])
            sjf_scores.append(scores["SJF"])
            priority_rr_max_wait = max(priority_rr_max_wait, results["Priority RR"].max_waiting_time)
        candidates.append(
            {
                **config,
                "validation_mean_score": mean(priority_rr_scores),
                "validation_sjf_mean_score": mean(sjf_scores),
                "validation_max_waiting_time": priority_rr_max_wait,
            }
        )
    selected = min(
        candidates,
        key=lambda candidate: (
            candidate["validation_mean_score"],
            candidate["validation_max_waiting_time"],
            candidate["quantum"],
            -candidate["aging_interval"],
        ),
    )
    return {"samples": len(validation_rows), "candidates": candidates, "selected": selected}
