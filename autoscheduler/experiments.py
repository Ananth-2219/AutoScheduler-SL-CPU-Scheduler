"""Held-out adaptive scheduler evaluation and artifacts."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from statistics import mean, median, pstdev

from autoscheduler.adaptive import run_adaptive
from autoscheduler.evaluation import ALGORITHMS, compare_algorithms, oracle_label
from autoscheduler.features import FEATURE_NAMES
from autoscheduler.workloads import PROFILES, generate_workload


def _score_column(algorithm: str) -> str:
    return f"score_{algorithm.lower().replace(' ', '_')}"


def _label_distribution(rows: list[dict], key: str) -> dict[str, dict[str, int]]:
    return {
        profile: {algorithm: sum(row[key] == algorithm for row in rows if row["profile"] == profile)
                  for algorithm in ALGORITHMS}
        for profile in PROFILES
    }


def _confusion_matrix(rows: list[dict]) -> dict[str, dict[str, int]]:
    return {
        oracle: {selected: sum(row["oracle"] == oracle and row["selected"] == selected for row in rows)
                 for selected in ALGORITHMS}
        for oracle in ALGORITHMS
    }


def evaluate_model(
    model, samples_per_profile: int = 200, seed: int = 2026, priority_rr_config: dict | None = None
) -> tuple[list[dict], dict]:
    rows = []
    for profile_index, profile in enumerate(PROFILES):
        for sample_index in range(samples_per_profile):
            workload_seed = seed * 10_000_000 + profile_index * 1_000_000 + sample_index
            workload = generate_workload(profile, workload_seed)
            results = compare_algorithms(workload.processes, priority_rr_config)
            oracle, scores = oracle_label(results)
            adaptive = run_adaptive(workload.processes, model)
            selected = adaptive.selected_algorithm
            row = {
                "profile": profile,
                "seed": workload_seed,
                "oracle": oracle,
                "selected": selected,
                "correct": int(selected == oracle),
                "regret": scores[selected] - scores[oracle],
                "inference_ms": adaptive.inference_ms,
            }
            row.update({f"score_{name.lower().replace(' ', '_')}": value for name, value in scores.items()})
            row.update(
                {
                    f"max_wait_{name.lower().replace(' ', '_')}": result.max_waiting_time
                    for name, result in results.items()
                }
            )
            row.update(
                {
                    f"switch_time_{name.lower().replace(' ', '_')}": result.context_switch_time
                    for name, result in results.items()
                }
            )
            rows.append(row)

    def summarize(group: list[dict]) -> dict:
        regrets = [row["regret"] for row in group]
        return {
            "samples": len(group),
            "accuracy": mean(row["correct"] for row in group),
            "mean_regret": mean(regrets),
            "median_regret": median(regrets),
            "regret_stddev": pstdev(regrets),
            "mean_inference_ms": mean(row["inference_ms"] for row in group),
            "mean_score": mean(row[_score_column(row["selected"])] for row in group),
        }

    static_scores = {
        name: mean(row[f"score_{name.lower().replace(' ', '_')}"] for row in rows)
        for name in ALGORITHMS
    }
    adaptive_summary = summarize(rows)
    sjf_rows = [
        {
            **row,
            "selected": "SJF",
            "correct": int(row["oracle"] == "SJF"),
            "regret": row["score_sjf"] - row[_score_column(row["oracle"])],
            "inference_ms": 0.0,
        }
        for row in rows
    ]
    constant_sjf = summarize(sjf_rows)
    static_policies = {
        algorithm: {
            "mean_score": static_scores[algorithm],
            "mean_regret": mean(
                row[_score_column(algorithm)] - row[_score_column(row["oracle"])] for row in rows
            ),
            "accuracy": mean(row["oracle"] == algorithm for row in rows),
            "max_waiting_time": max(row[f"max_wait_{algorithm.lower().replace(' ', '_')}"] for row in rows),
            "mean_context_switch_time": mean(
                row[f"switch_time_{algorithm.lower().replace(' ', '_')}"] for row in rows
            ),
        }
        for algorithm in ALGORITHMS
    }
    feature_values = getattr(model, "feature_importances_", [0.0] * len(FEATURE_NAMES))
    summary = {
        **adaptive_summary,
        "adaptive": adaptive_summary,
        "constant_sjf": constant_sjf,
        "static_policies": static_policies,
        "oracle": {
            "mean_score": mean(row[_score_column(row["oracle"])] for row in rows),
            "mean_regret": 0.0,
            "accuracy": 1.0,
        },
        "feature_importance": {
            name: float(value) for name, value in zip(FEATURE_NAMES, feature_values)
        },
        "oracle_label_distribution": _label_distribution(rows, "oracle"),
        "selected_label_distribution": _label_distribution(rows, "selected"),
        "confusion_matrix": _confusion_matrix(rows),
    }
    summary["per_profile"] = {
        profile: summarize([row for row in rows if row["profile"] == profile])
        for profile in PROFILES
    }
    summary["mean_static_scores"] = static_scores
    summary["best_static_algorithm"] = min(static_scores, key=static_scores.get)
    summary["mean_adaptive_score"] = adaptive_summary["mean_score"]
    summary["mean_oracle_score"] = summary["oracle"]["mean_score"]
    best_static_score = static_scores[summary["best_static_algorithm"]]
    summary["adaptive_improvement_vs_best_static"] = (
        best_static_score - summary["mean_adaptive_score"]
    )
    summary["adaptive_beats_best_static"] = summary["mean_adaptive_score"] < best_static_score
    summary["adaptive_beats_sjf"] = adaptive_summary["mean_score"] < constant_sjf["mean_score"]
    summary["eligible_for_next_adaptive_phase"] = summary["adaptive_beats_sjf"]
    priority_rr = static_policies["Priority RR"]
    sjf = static_policies["SJF"]
    summary["priority_rr_beats_sjf"] = (
        priority_rr["mean_score"] < sjf["mean_score"]
        and priority_rr["max_waiting_time"] < sjf["max_waiting_time"]
    )
    summary["priority_rr_config"] = priority_rr_config or ALGORITHMS["Priority RR"][1]
    return rows, summary


def save_evaluation(rows: list[dict], summary: dict, output_dir: str | Path) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "evaluation.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (output_dir / "confusion_matrix.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=("oracle", "selected", "count"))
        writer.writeheader()
        for oracle, selections in summary["confusion_matrix"].items():
            for selected, count in selections.items():
                writer.writerow({"oracle": oracle, "selected": selected, "count": count})
    with (output_dir / "feature_importance.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=("feature", "importance"))
        writer.writeheader()
        for feature, importance in sorted(
            summary["feature_importance"].items(), key=lambda item: item[1], reverse=True
        ):
            writer.writerow({"feature": feature, "importance": importance})

    cache_dir = Path(".cache/matplotlib").resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(cache_dir)
    os.environ["XDG_CACHE_HOME"] = str(cache_dir)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(summary["mean_static_scores"]) + ["Adaptive", "Oracle"]
    values = list(summary["mean_static_scores"].values()) + [
        summary["mean_adaptive_score"],
        summary["mean_oracle_score"],
    ]
    figure, axis = plt.subplots(figsize=(8, 4))
    axis.bar(labels, values)
    axis.set_ylabel("Mean weighted score (lower is better)")
    axis.tick_params(axis="x", rotation=25)
    figure.tight_layout()
    figure.savefig(output_dir / "scores.png")
    plt.close(figure)

    figure, (labels_axis, importance_axis) = plt.subplots(1, 2, figsize=(11, 4))
    labels = list(ALGORITHMS)
    labels_axis.bar(labels, [sum(counts[label] for counts in summary["oracle_label_distribution"].values())
                             for label in labels], label="Oracle")
    labels_axis.bar(labels, [sum(counts[label] for counts in summary["selected_label_distribution"].values())
                             for label in labels], alpha=0.6, label="Selected")
    labels_axis.set_ylabel("Workloads")
    labels_axis.tick_params(axis="x", rotation=25)
    labels_axis.legend()
    ranked = sorted(summary["feature_importance"].items(), key=lambda item: item[1])
    importance_axis.barh([name for name, _ in ranked], [value for _, value in ranked])
    importance_axis.set_xlabel("Decision-tree importance")
    figure.tight_layout()
    figure.savefig(output_dir / "diagnostics.png")
    plt.close(figure)
