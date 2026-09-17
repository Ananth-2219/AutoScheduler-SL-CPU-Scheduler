"""Validation-only tuning for the Priority Round Robin baseline."""

from __future__ import annotations

import random
from statistics import mean

from autoscheduler.evaluation import ALGORITHMS, compare_algorithms, score_results
from autoscheduler.workloads import PROFILES, generate_workload


PRIORITY_RR_GRID = tuple(
    {"quantum": quantum, "aging_interval": aging_interval, "context_switch_cost": 1}
    for quantum in (1, 2, 4)
    for aging_interval in (4, 8, 12)
)


def _validation_workloads(samples_per_profile: int, seed: int):
    if samples_per_profile <= 0:
        raise ValueError("samples_per_profile must be positive")
    count = max(1, round(samples_per_profile * 0.15))
    workloads = []
    for profile_index, profile in enumerate(PROFILES):
        indexes = list(range(samples_per_profile))
        random.Random(seed + profile_index).shuffle(indexes)
        for sample_index in sorted(indexes[:count]):
            workload_seed = seed * 10_000_000 + profile_index * 1_000_000 + sample_index
            workloads.append(generate_workload(profile, workload_seed))
    return workloads


def tune_priority_rr(samples_per_profile: int = 500, seed: int = 42) -> dict:
    """Select a Priority-RR configuration using only the fixed validation split."""
    validation_workloads = _validation_workloads(samples_per_profile, seed)
    candidates = []
    for config in PRIORITY_RR_GRID:
        priority_rr_scores = []
        sjf_scores = []
        priority_rr_max_wait = 0
        for workload in validation_workloads:
            results = compare_algorithms(workload.processes, priority_rr_config=config)
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
    return {
        "samples": len(validation_workloads),
        "seed": seed,
        "policy_set": list(ALGORITHMS),
        "candidates": candidates,
        "selected": selected,
    }
