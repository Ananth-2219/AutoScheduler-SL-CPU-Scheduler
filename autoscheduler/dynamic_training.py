"""Grouped synthetic development training, including train-only on-policy states."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from autoscheduler.dynamic import (
    DYNAMIC_FEATURE_NAMES, DynamicRouterConfig, build_dynamic_dataset,
    dynamic_policy_names, generate_dynamic_workload, run_dynamic, _percentile,
)
from autoscheduler.evaluation import ALGORITHMS, compare_algorithms, score_result_against_reference
from autoscheduler.fairness import aggregate_fairness
from autoscheduler.model import _split_indexes


def build_training_data(
    traces: int, seed: int, config: DynamicRouterConfig, manifest_path: str | Path,
    priority_rr_config: dict | None = None,
    development: bool = False,
) -> tuple[list[dict], dict]:
    """Write groups before fitting; augment only the training partition."""
    from sklearn.tree import DecisionTreeClassifier

    rows = build_dynamic_dataset(traces, seed, config, priority_rr_config, development=development)
    indexes = _split_indexes(rows, seed, "seed")
    groups = {
        name: sorted({rows[index]["seed"] for index in split})
        for name, split in zip(("train", "validation", "test"), indexes)
    }
    manifest = {
        "status": "SYNTHETIC_DEVELOPMENT_ONLY", "seed": seed,
        "group_key": "seed", "groups": groups,
        "occupancy": "mixed_static_and_exploration_plus_train_only_pilot_rollouts",
        "pilot": {"max_depth": 5, "min_samples_leaf": 10},
    }
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    train_rows = [rows[index] for index in indexes[0]]
    pilot = DecisionTreeClassifier(max_depth=5, min_samples_leaf=10, random_state=seed).fit(
        [[row[name] for name in DYNAMIC_FEATURE_NAMES] for row in train_rows],
        [row["label"] for row in train_rows],
    )
    on_policy = build_dynamic_dataset(
        traces, seed, config, priority_rr_config, behavior_model=pilot,
        trace_indexes=[trace_seed - seed * 1_000_000 for trace_seed in groups["train"]],
        development=development,
    )
    assert {row["seed"] for row in on_policy} <= set(groups["train"])
    rows += on_policy
    return rows, {**manifest, "mixed_rows": len(rows) - len(on_policy), "on_policy_rows": len(on_policy)}


def prepare_validation(traces: int, seed: int, config: DynamicRouterConfig, priority_rr_config=None,
                       development: bool = False):
    """Freeze whole-workload static comparisons before assessing a candidate."""
    policies = dynamic_policy_names(config)
    cases = []
    scores = {policy: [] for policy in policies}
    for index in range(traces):
        if development:
            from autoscheduler.development_workloads import DEV_FAMILIES, generate_development_workload
            workload = generate_development_workload(seed * 1_000_000 + index,
                                                      DEV_FAMILIES[index % len(DEV_FAMILIES)])
        else:
            workload = generate_dynamic_workload(seed * 1_000_000 + index)
        results = compare_algorithms(workload.processes, priority_rr_config,
                                     tuple(dict.fromkeys((*ALGORITHMS, *policies))))
        references = {policy: results[policy] for policy in ALGORITHMS}
        for policy in policies:
            scores[policy].append(score_result_against_reference(results[policy], references))
        cases.append((workload, results, references))
    means = {policy: mean(values) for policy, values in scores.items()}
    comparator = min(policies, key=lambda policy: (means[policy], policies.index(policy)))
    return cases, {"seed": seed, "traces": traces, "static_scores": means, "static_baseline": comparator}


def validation_metrics(model, cases, config: DynamicRouterConfig, priority_rr_config=None) -> dict:
    """Candidate selection uses realized schedules on development workloads."""
    scores, responses, starvations = [], [], []
    for workload, _, references in cases:
        result = run_dynamic(workload.processes, model, config, priority_rr_config)
        scores.append(score_result_against_reference(result.simulation, references))
        responses.append(_percentile([metric.response_time for metric in result.simulation.process_metrics], .95))
        starvations.append(aggregate_fairness(result.simulation.process_metrics)["starvation_count"])
    return {
        "validation_schedule_score": mean(scores),
        "validation_schedule_p95_response": mean(responses),
        "validation_schedule_starvation": mean(starvations),
    }
