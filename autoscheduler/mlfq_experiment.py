"""Static MLFQ comparison against tuned RR, SRTF, and fixed hybrid."""

from __future__ import annotations

import csv
import json
import os
import random
from pathlib import Path
from statistics import mean

from autoscheduler.benefit import (
    _full_rr,
    _reference,
    _score,
    _tune_rr,
    _workloads,
    run_fixed_hybrid,
)
from autoscheduler.experiments import paired_bootstrap_ci
from autoscheduler.fairness import FAIRNESS_FIELDS, aggregate_fairness
from autoscheduler.latency import SIZES, _stats
from autoscheduler.workloads import PROFILES, generate_workload
from scheduler.mlfq import mlfq
from scheduler.srtf import srtf
from simulator.simulator import run_simulation
from simulator.engine import simulate


POLICIES = ("Tuned RR", "SRTF", "RR20-SRTF", "MLFQ")
MLFQ_CONFIG = {"quanta": (2, 4, 8), "aging_threshold": 20, "context_switch_cost": 0}
PROCESS_COUNT_RANGES = {
    "interactive": (16, 32), "batch": (10, 24), "cpu_intensive": (8, 20),
    "io_intensive": (16, 32), "mixed": (12, 32),
}


def _slug(name: str) -> str:
    return name.lower().replace("-", "_").replace(" ", "_")


def _evaluation_workloads(samples_per_profile: int, seed: int):
    if samples_per_profile <= 0:
        raise ValueError("samples_per_profile must be positive")
    workloads = []
    for profile_index, profile in enumerate(PROFILES):
        for sample in range(samples_per_profile):
            workload_seed = seed * 10_000_000 + profile_index * 1_000_000 + sample
            count = random.Random(workload_seed).randint(*PROCESS_COUNT_RANGES[profile])
            workloads.append(generate_workload(profile, workload_seed, count))
    return workloads


def _run_policies(processes, rr_quantum: int):
    return {
        "Tuned RR": _full_rr(processes, rr_quantum),
        "SRTF": run_simulation("SRTF", srtf, list(processes)),
        "RR20-SRTF": run_fixed_hybrid(processes, rr_quantum, 20),
        "MLFQ": run_simulation("MLFQ", mlfq, list(processes), **MLFQ_CONFIG),
    }


def evaluate_mlfq(
    samples_per_profile: int = 200, seed: int = 6060,
    tuning_samples_per_profile: int = 500, tuning_seed: int = 42,
    bootstrap_samples: int = 10_000, bootstrap_seed: int = 6061,
) -> tuple[list[dict], dict]:
    development = _workloads(tuning_samples_per_profile, tuning_seed)
    development_references = [_reference(workload) for workload in development]
    rr_quantum, rr_candidates = _tune_rr(
        development, list(range(len(development))), development_references
    )
    rows = []
    fairness = {name: [] for name in POLICIES}
    profile_fairness = {
        profile: {name: [] for name in POLICIES} for profile in PROFILES
    }
    for workload in _evaluation_workloads(samples_per_profile, seed):
        reference = _reference(workload)
        results = _run_policies(workload.processes, rr_quantum)
        scores = {name: _score(result, reference) for name, result in results.items()}
        row = {"profile": workload.profile, "seed": workload.seed, "process_count": len(workload.processes)}
        for name, result in results.items():
            slug = _slug(name)
            row.update({
                f"score_{slug}": scores[name],
                f"response_{slug}": result.avg_response_time,
                f"context_switches_{slug}": result.context_switches,
            })
            fairness[name].extend(result.process_metrics)
            profile_fairness[workload.profile][name].extend(result.process_metrics)
        rows.append(row)

    def summarize(group: list[dict], metrics_by_policy=None) -> dict:
        policy_summary = {}
        for name in POLICIES:
            slug = _slug(name)
            item = {
                "mean_score": mean(row[f"score_{slug}"] for row in group),
                "mean_response_time": mean(row[f"response_{slug}"] for row in group),
                "mean_context_switches": mean(row[f"context_switches_{slug}"] for row in group),
            }
            if metrics_by_policy is not None:
                item.update(aggregate_fairness(metrics_by_policy[name]))
            policy_summary[name] = item
        return policy_summary

    policies = summarize(rows, fairness)
    best_comparator = min(POLICIES[:-1], key=lambda name: policies[name]["mean_score"])
    differences = {
        name: paired_bootstrap_ci(
            [row["score_mlfq"] - row[f"score_{_slug(name)}"] for row in rows],
            bootstrap_samples, bootstrap_seed,
        )
        for name in POLICIES[:-1]
    }
    best_score = policies[best_comparator]["mean_score"]
    mlfq_score = policies["MLFQ"]["mean_score"]
    best_difference = differences[best_comparator]
    statistical_tie = (
        mlfq_score <= best_score * 1.01
        and best_difference["ci_low"] <= 0 <= best_difference["ci_high"]
    )
    score_gate = mlfq_score <= best_score or statistical_tie
    fairness_gate = (
        policies["MLFQ"]["p95_waiting_time"] <= policies["Tuned RR"]["p95_waiting_time"]
        and policies["MLFQ"]["starvation_count"] <= policies["Tuned RR"]["starvation_count"]
    )
    per_profile = {}
    profile_wins = profile_losses = 0
    for profile in PROFILES:
        group = [row for row in rows if row["profile"] == profile]
        profile_policies = summarize(group, profile_fairness[profile])
        profile_best = min(POLICIES[:-1], key=lambda name: profile_policies[name]["mean_score"])
        profile_difference = profile_policies["MLFQ"]["mean_score"] - profile_policies[profile_best]["mean_score"]
        profile_wins += profile_difference < 0
        profile_losses += profile_difference > 0
        per_profile[profile] = {
            "policies": profile_policies,
            "best_comparator": profile_best,
            "mlfq_difference_vs_best": paired_bootstrap_ci(
                [row["score_mlfq"] - row[f"score_{_slug(profile_best)}"] for row in group],
                bootstrap_samples, bootstrap_seed,
            ),
        }
    return rows, {
        "samples": len(rows), "seed": seed, "bootstrap_seed": bootstrap_seed,
        "rr_quantum": rr_quantum, "rr_quantum_candidates": rr_candidates,
        "mlfq_config": MLFQ_CONFIG, "policies": policies,
        "best_comparator": best_comparator, "paired_mlfq_differences": differences,
        "score_gate": score_gate, "fairness_gate": fairness_gate,
        "profile_wins": profile_wins, "profile_losses": profile_losses,
        "per_profile": per_profile, "latency_status": "pending",
    }


def run_mlfq_latency(
    rr_quantum: int, samples_per_profile: int = 20, seed: int = 6062, warmups: int = 5,
) -> tuple[list[dict], dict]:
    if rr_quantum <= 0 or samples_per_profile <= 0 or warmups < 0:
        raise ValueError("quantum and samples must be positive; warmups must be non-negative")
    measurements = {name: {size: [] for size in SIZES} for name in POLICIES}
    for size_index, (size, count) in enumerate(SIZES.items()):
        for profile_index, profile in enumerate(PROFILES):
            for sample in range(samples_per_profile + warmups):
                workload = generate_workload(
                    profile,
                    seed * 10_000_000 + size_index * 1_000_000 + profile_index * 100_000 + sample,
                    count,
                )
                timings = {name: [] for name in POLICIES}
                simulate(workload.processes, "rr", quantum=rr_quantum, decision_times_ns=timings["Tuned RR"])
                simulate(workload.processes, "srtf", preemptive=True, decision_times_ns=timings["SRTF"])
                run_fixed_hybrid(workload.processes, rr_quantum, 20, timings["RR20-SRTF"])
                mlfq(workload.processes, decision_times_ns=timings["MLFQ"], **MLFQ_CONFIG)
                if sample >= warmups:
                    for name in POLICIES:
                        measurements[name][size].extend(value / 1_000_000 for value in timings[name])
    latency = {
        name: {size: _stats(values) for size, values in sizes.items()}
        for name, sizes in measurements.items()
    }
    policy_gate = {
        name: {"passes_gate": all(latency[name][size]["p99_ms"] < 10.0 for size in SIZES)}
        for name in POLICIES
    }
    rows = [
        {"policy": name, "size": size, **stats, "passes_gate": stats["p99_ms"] < 10.0}
        for name, sizes in latency.items()
        for size, stats in sizes.items()
    ]
    return rows, {
        "seed": seed, "samples_per_profile": samples_per_profile, "warmups": warmups,
        "sizes": SIZES, "latency": latency, "policy_gate": policy_gate,
    }


def finalize_mlfq_summary(evaluation: dict, latency_summary: dict) -> dict:
    decision = apply_decision_gates(evaluation, latency_summary["policy_gate"])
    evaluation.update(decision)
    evaluation["latency_status"] = "complete"
    evaluation["latency_gate"] = latency_summary["policy_gate"]
    return evaluation


def _plotter():
    cache = Path(".cache/matplotlib").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = os.environ["XDG_CACHE_HOME"] = str(cache)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def save_mlfq_evaluation(rows: list[dict], summary: dict, output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "evaluation.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (output / "fairness.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=("policy", *FAIRNESS_FIELDS))
        writer.writeheader()
        for name, metrics in summary["policies"].items():
            writer.writerow({"policy": name, **{field: metrics[field] for field in FAIRNESS_FIELDS}})
    plt = _plotter()
    figure, axis = plt.subplots(figsize=(8, 4))
    axis.bar(POLICIES, [summary["policies"][name]["mean_score"] for name in POLICIES])
    axis.set_ylabel("Mean fixed-anchor score (lower is better)")
    axis.tick_params(axis="x", rotation=20)
    figure.tight_layout()
    figure.savefig(output / "scores.png")
    plt.close(figure)


def save_mlfq_latency(rows: list[dict], summary: dict, output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "latency.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    (output / "latency_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    plt = _plotter()
    figure, axis = plt.subplots(figsize=(8, 4))
    size_labels = list(SIZES)
    for name in POLICIES:
        axis.plot(size_labels, [summary["latency"][name][size]["p99_ms"] for size in size_labels], marker="o", label=name)
    axis.axhline(10.0, color="red", linestyle="--", label="10 ms gate")
    axis.set_ylabel("P99 decision latency (ms)")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(output / "latency.png")
    plt.close(figure)


def apply_decision_gates(evaluation: dict, latency: dict) -> dict:
    """Combine score, fairness, and strict latency evidence."""
    mlfq_latency = latency["MLFQ"]["passes_gate"]
    mlfq_wins = evaluation["score_gate"] and evaluation["fairness_gate"] and mlfq_latency
    profile_opportunity = bool(
        not mlfq_wins
        and evaluation["fairness_gate"]
        and mlfq_latency
        and evaluation["profile_wins"] >= 2
        and evaluation["profile_losses"] >= 1
    )
    passing = [name for name in POLICIES if latency[name]["passes_gate"]]
    recommended = min(passing, key=lambda name: evaluation["policies"][name]["mean_score"]) if passing else None
    if mlfq_wins:
        recommended = "MLFQ"
    return {
        "mlfq_wins": mlfq_wins,
        "profile_tuning_opportunity": profile_opportunity,
        "recommend_ml_next": mlfq_wins or profile_opportunity,
        "recommended_policy": recommended,
        "ml_next_step": "predict_initial_queue_or_quantum" if mlfq_wins or profile_opportunity else "do_not_add_ml",
    }
