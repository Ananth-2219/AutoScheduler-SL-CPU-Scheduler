"""Held-out adaptive scheduler evaluation and artifacts."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from statistics import mean, median, pstdev

from autoscheduler.adaptive import run_adaptive
from autoscheduler.evaluation import ALGORITHMS, compare_algorithms, oracle_label
from autoscheduler.workloads import PROFILES, generate_workload


def evaluate_model(model, samples_per_profile: int = 200, seed: int = 2026) -> tuple[list[dict], dict]:
    rows = []
    for profile_index, profile in enumerate(PROFILES):
        for sample_index in range(samples_per_profile):
            workload_seed = seed * 10_000_000 + profile_index * 1_000_000 + sample_index
            workload = generate_workload(profile, workload_seed)
            results = compare_algorithms(workload.processes)
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
        }

    static_scores = {
        name: mean(row[f"score_{name.lower().replace(' ', '_')}"] for row in rows)
        for name in ALGORITHMS
    }
    summary = summarize(rows)
    summary["per_profile"] = {
        profile: summarize([row for row in rows if row["profile"] == profile])
        for profile in PROFILES
    }
    summary["mean_static_scores"] = static_scores
    summary["best_static_algorithm"] = min(static_scores, key=static_scores.get)
    summary["mean_adaptive_score"] = mean(
        row[f"score_{row['selected'].lower().replace(' ', '_')}"] for row in rows
    )
    summary["mean_oracle_score"] = mean(
        row[f"score_{row['oracle'].lower().replace(' ', '_')}"] for row in rows
    )
    best_static_score = static_scores[summary["best_static_algorithm"]]
    summary["adaptive_improvement_vs_best_static"] = (
        best_static_score - summary["mean_adaptive_score"]
    )
    summary["adaptive_beats_best_static"] = summary["mean_adaptive_score"] < best_static_score
    return rows, summary


def save_evaluation(rows: list[dict], summary: dict, output_dir: str | Path) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "evaluation.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

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
