"""One-shot RR-versus-SRTF benefit routing from observed runtime state."""

from __future__ import annotations

import copy
import csv
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pvariance
from time import perf_counter_ns
from typing import Iterable

from autoscheduler.dynamic import _dispatch, _new_state, _policy_config, _release, _run_to_completion, _simulation
from autoscheduler.evaluation import ALGORITHMS, compare_algorithms, score_result_against_reference
from autoscheduler.experiments import paired_bootstrap_ci
from autoscheduler.latency import percentile
from autoscheduler.workloads import PROFILES, generate_workload
from scheduler.srtf import srtf
from simulator.process import Process
from simulator.simulator import SimulationResult, run_simulation


BENEFIT_FEATURE_NAMES = (
    "elapsed_time", "arrivals_seen", "observed_arrival_rate", "ready_count", "blocked_count",
    "ready_wait_mean", "ready_wait_max", "priority_mean", "priority_variance",
    "service_mean", "service_variance", "completed_burst_mean", "completed_burst_variance",
    "short_completed_burst_ratio", "io_returns", "io_return_ratio", "context_switches",
)
RR_QUANTA = (1, 2, 4, 8)
OBSERVATION_WINDOWS = (5, 10, 20)
SWITCH_MARGINS = (0.0, 0.0025, 0.005, 0.01, 0.02)
BENEFIT_SIZES = {"small": 12, "medium": 100, "large": 1_000}
FROZEN_SIX_POLICY_PRIORITY_RR = {"quantum": 1, "aging_interval": 4, "context_switch_cost": 1}


@dataclass(frozen=True)
class BenefitConfig:
    rr_quantum: int
    observation_ticks: int
    margin: float

    def __post_init__(self):
        if self.rr_quantum <= 0 or self.observation_ticks < 0 or self.margin < 0:
            raise ValueError("quantum must be positive; observation and margin must be non-negative")


@dataclass
class BenefitResult:
    simulation: SimulationResult
    selected_policy: str
    predicted_delta: float | None
    features: dict[str, float]
    inference_ms: float


def _rr_config(quantum: int) -> dict:
    return {**_policy_config(None), "quantum": quantum, "context_switch_cost": 0}


def _observe(
    processes: Iterable[Process], config: BenefitConfig,
    decision_times_ns: list[int] | None = None,
):
    state = _new_state(processes)
    _release(state, state.current_time)
    rr_config = _rr_config(config.rr_quantum)
    while (state.pending or state.ready or state.blocked) and state.current_time < config.observation_ticks:
        _dispatch(state, "Round Robin", rr_config, decision_times_ns)
    _release(state, state.current_time)
    return state


def extract_observed_features(state) -> dict[str, float]:
    seen = [item.process for item in state.ready]
    seen.extend(process for _, process, _, _ in state.blocked)
    seen.extend(state.completed)
    priorities = [process.priority for process in seen]
    waits = [max(0, state.current_time - item.time) for item in state.ready]
    service_by_pid: dict[str, int] = {}
    process_timeline = [entry for entry in state.timeline if entry[0] != "CS"]
    for pid, start, end in process_timeline:
        service_by_pid[pid] = service_by_pid.get(pid, 0) + end - start
    service = list(service_by_pid.values())
    bursts = state.completed_burst_durations
    switches = sum(left[0] != right[0] for left, right in zip(process_timeline, process_timeline[1:]))
    return {
        "elapsed_time": float(state.current_time),
        "arrivals_seen": float(state.arrivals_seen),
        "observed_arrival_rate": state.arrivals_seen / max(1, state.current_time),
        "ready_count": float(len(state.ready)), "blocked_count": float(len(state.blocked)),
        "ready_wait_mean": mean(waits) if waits else 0.0, "ready_wait_max": max(waits, default=0.0),
        "priority_mean": mean(priorities) if priorities else 0.0,
        "priority_variance": pvariance(priorities) if priorities else 0.0,
        "service_mean": mean(service) if service else 0.0,
        "service_variance": pvariance(service) if service else 0.0,
        "completed_burst_mean": mean(bursts) if bursts else 0.0,
        "completed_burst_variance": pvariance(bursts) if bursts else 0.0,
        "short_completed_burst_ratio": sum(value <= 4 for value in bursts) / len(bursts) if bursts else 0.0,
        "io_returns": float(state.total_io_returns),
        "io_return_ratio": state.total_io_returns / max(1, state.arrivals_seen + state.total_io_returns),
        "context_switches": float(switches),
    }


def _complete(
    state, policy: str, config: BenefitConfig,
    decision_times_ns: list[int] | None = None,
) -> SimulationResult:
    trial = copy.deepcopy(state)
    _run_to_completion(trial, policy, _rr_config(config.rr_quantum), decision_times_ns)
    return _simulation(trial, policy)


def run_fixed_hybrid(
    processes: Iterable[Process], rr_quantum: int = 1, observation_ticks: int = 20,
    decision_times_ns: list[int] | None = None,
) -> SimulationResult:
    """Run RR until first dispatch boundary after observation, then SRTF."""
    config = BenefitConfig(rr_quantum, observation_ticks, 0.0)
    state = _observe(processes, config, decision_times_ns)
    result = _complete(state, "SRTF", config, decision_times_ns)
    result.algorithm = "RR20-SRTF"
    return result


def run_benefit(processes: Iterable[Process], model, config: BenefitConfig) -> BenefitResult:
    state = _observe(processes, config)
    if not (state.pending or state.ready or state.blocked):
        features = extract_observed_features(state)
        return BenefitResult(_simulation(state, "RR Benefit"), "Round Robin", None, features, 0.0)
    started = perf_counter_ns()
    features = extract_observed_features(state)
    predicted = float(model.predict([[features[name] for name in BENEFIT_FEATURE_NAMES]])[0])
    inference_ms = (perf_counter_ns() - started) / 1_000_000
    selected = "SRTF" if predicted < -config.margin else "Round Robin"
    return BenefitResult(_complete(state, selected, config), selected, predicted, features, inference_ms)


def _workloads(samples_per_profile: int, seed: int, process_count: int | None = None):
    if samples_per_profile <= 0:
        raise ValueError("samples_per_profile must be positive")
    return [
        generate_workload(
            profile,
            seed * 10_000_000 + profile_index * 1_000_000 + sample,
            process_count,
        )
        for profile_index, profile in enumerate(PROFILES)
        for sample in range(samples_per_profile)
    ]


def _split_workloads(workloads, seed: int):
    splits = {"train": [], "validation": [], "test": []}
    randomizer = random.Random(seed)
    for profile in PROFILES:
        indexes = [index for index, workload in enumerate(workloads) if workload.profile == profile]
        if len(indexes) < 4:
            raise ValueError("benefit training requires at least four workloads per profile")
        randomizer.shuffle(indexes)
        train_end = int(len(indexes) * 0.70)
        validation_end = train_end + (len(indexes) - train_end) // 2
        splits["train"].extend(indexes[:train_end])
        splits["validation"].extend(indexes[train_end:validation_end])
        splits["test"].extend(indexes[validation_end:])
    seed_sets = {name: {workloads[index].seed for index in values} for name, values in splits.items()}
    assert not (seed_sets["train"] & seed_sets["validation"] or seed_sets["train"] & seed_sets["test"] or seed_sets["validation"] & seed_sets["test"])
    return splits


def _reference(workload):
    return compare_algorithms(workload.processes, FROZEN_SIX_POLICY_PRIORITY_RR)


def _score(result, reference) -> float:
    return score_result_against_reference(result, reference, ALGORITHMS)


def _full_rr(processes, quantum: int) -> SimulationResult:
    state = _new_state(processes)
    _run_to_completion(state, "Round Robin", _rr_config(quantum))
    return _simulation(state, f"Round Robin (q={quantum})")


def _tune_rr(workloads, train_indexes, references) -> tuple[int, list[dict]]:
    candidates = []
    for quantum in RR_QUANTA:
        value = mean(_score(_full_rr(workloads[index].processes, quantum), references[index]) for index in train_indexes)
        candidates.append({"quantum": quantum, "mean_score": value})
    selected = min(candidates, key=lambda row: (row["mean_score"], -row["quantum"]))["quantum"]
    return selected, candidates


def _benefit_row(workload, reference, quantum: int, window: int) -> dict:
    config = BenefitConfig(quantum, window, 0.0)
    state = _observe(workload.processes, config)
    features = extract_observed_features(state)
    rr_result = _complete(state, "Round Robin", config)
    srtf_result = _complete(state, "SRTF", config)
    rr_score, srtf_score = _score(rr_result, reference), _score(srtf_result, reference)
    return {
        **features,
        "profile": workload.profile,
        "seed": workload.seed,
        "observation_ticks": window,
        "completed_before_decision": int(not (state.pending or state.ready or state.blocked)),
        "rr_score": rr_score,
        "srtf_score": srtf_score,
        "target_delta": srtf_score - rr_score,
    }


def _selection_score(rows: list[dict], predictions, margin: float) -> float:
    return mean(
        row["srtf_score"] if prediction < -margin else row["rr_score"]
        for row, prediction in zip(rows, predictions)
    )


def train_benefit(
    samples_per_profile: int = 500,
    seed: int = 42,
    model_path: str | Path = "results/rr_srtf_benefit/model.joblib",
    dataset_path: str | Path = "results/rr_srtf_benefit/training.csv",
) -> dict:
    import joblib
    from sklearn.tree import DecisionTreeRegressor

    workloads = _workloads(samples_per_profile, seed)
    splits = _split_workloads(workloads, seed)
    references = [_reference(workload) for workload in workloads]
    quantum, quantum_candidates = _tune_rr(workloads, splits["train"], references)
    rows_by_window = {
        window: [_benefit_row(workload, reference, quantum, window) for workload, reference in zip(workloads, references)]
        for window in OBSERVATION_WINDOWS
    }
    candidates = []
    best = None
    for window in OBSERVATION_WINDOWS:
        rows = rows_by_window[window]
        train_rows = [rows[index] for index in splits["train"]]
        validation_rows = [rows[index] for index in splits["validation"]]
        train_x = [[row[name] for name in BENEFIT_FEATURE_NAMES] for row in train_rows]
        train_y = [row["target_delta"] for row in train_rows]
        validation_x = [[row[name] for name in BENEFIT_FEATURE_NAMES] for row in validation_rows]
        for depth_rank, depth in enumerate((3, 5, 8, None)):
            for leaf in (10, 5, 1):
                model = DecisionTreeRegressor(max_depth=depth, min_samples_leaf=leaf, random_state=seed).fit(train_x, train_y)
                predictions = model.predict(validation_x)
                for margin in SWITCH_MARGINS:
                    item = {
                        "observation_ticks": window,
                        "max_depth": depth,
                        "min_samples_leaf": leaf,
                        "margin": margin,
                        "validation_mean_score": _selection_score(validation_rows, predictions, margin),
                    }
                    candidates.append(item)
                    key = (item["validation_mean_score"], window, depth_rank, -leaf, -margin)
                    if best is None or key < best[0]:
                        best = (key, item)
    selected = best[1]
    selected_rows = rows_by_window[selected["observation_ticks"]]
    fit_indexes = splits["train"] + splits["validation"]
    model = DecisionTreeRegressor(
        max_depth=selected["max_depth"], min_samples_leaf=selected["min_samples_leaf"], random_state=seed
    ).fit(
        [[selected_rows[index][name] for name in BENEFIT_FEATURE_NAMES] for index in fit_indexes],
        [selected_rows[index]["target_delta"] for index in fit_indexes],
    )
    test_rows = [selected_rows[index] for index in splits["test"]]
    test_predictions = model.predict([[row[name] for name in BENEFIT_FEATURE_NAMES] for row in test_rows])
    config = BenefitConfig(quantum, selected["observation_ticks"], selected["margin"])
    metadata = {
        "seed": seed,
        "samples_per_profile": samples_per_profile,
        "config": config.__dict__,
        "features": list(BENEFIT_FEATURE_NAMES),
        "reference_priority_rr_config": FROZEN_SIX_POLICY_PRIORITY_RR,
        "rr_quantum_candidates": quantum_candidates,
        "selected_tree": {key: selected[key] for key in ("max_depth", "min_samples_leaf")},
        "validation_mean_score": selected["validation_mean_score"],
        "internal_test_mean_score": _selection_score(test_rows, test_predictions, config.margin),
        "internal_test_rr_score": mean(row["rr_score"] for row in test_rows),
        "split": {name: [workloads[index].seed for index in indexes] for name, indexes in splits.items()},
        "split_trace_counts": {name: len(indexes) for name, indexes in splits.items()},
        "feature_importance": dict(zip(BENEFIT_FEATURE_NAMES, map(float, model.feature_importances_))),
        "candidates": candidates,
    }
    model_path, dataset_path = Path(model_path), Path(dataset_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": BENEFIT_FEATURE_NAMES, "metadata": metadata}, model_path)
    model_path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with dataset_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=selected_rows[0])
        writer.writeheader()
        writer.writerows(selected_rows)
    return metadata


def load_benefit_model(path: str | Path):
    import joblib

    bundle = joblib.load(path)
    if tuple(bundle.get("features", ())) != BENEFIT_FEATURE_NAMES:
        raise ValueError("benefit model feature schema does not match current code")
    return bundle["model"], bundle["metadata"]


def evaluate_benefit(
    model,
    config: BenefitConfig,
    samples_per_profile: int = 200,
    seed: int = 4040,
    bootstrap_samples: int = 10_000,
    bootstrap_seed: int = 4041,
) -> tuple[list[dict], dict]:
    rows = []
    for workload in _workloads(samples_per_profile, seed):
        reference = _reference(workload)
        state = _observe(workload.processes, config)
        rr_result, continuation_srtf = _complete(state, "Round Robin", config), _complete(state, "SRTF", config)
        rr_score, continuation_srtf_score = _score(rr_result, reference), _score(continuation_srtf, reference)
        direct_srtf_score = _score(run_simulation("SRTF", srtf, list(workload.processes)), reference)
        if state.pending or state.ready or state.blocked:
            started = perf_counter_ns()
            features = extract_observed_features(state)
            predicted = float(model.predict([[features[name] for name in BENEFIT_FEATURE_NAMES]])[0])
            inference_ms = (perf_counter_ns() - started) / 1_000_000
            selected = "SRTF" if predicted < -config.margin else "Round Robin"
        else:
            features = extract_observed_features(state)
            predicted, inference_ms, selected = None, 0.0, "Round Robin"
        benefit_score = continuation_srtf_score if selected == "SRTF" else rr_score
        oracle_score = min(rr_score, continuation_srtf_score)
        rows.append({
            "profile": workload.profile, "seed": workload.seed, "selected": selected,
            "predicted_delta": predicted, "actual_delta": continuation_srtf_score - rr_score,
            "rr_score": rr_score, "direct_srtf_score": direct_srtf_score,
            "continuation_srtf_score": continuation_srtf_score, "benefit_score": benefit_score,
            "continuation_oracle_score": oracle_score, "difference_vs_rr": benefit_score - rr_score,
            "false_switch": int(selected == "SRTF" and continuation_srtf_score >= rr_score),
            "missed_srtf_opportunity": int(selected == "Round Robin" and continuation_srtf_score < rr_score),
            "inference_ms": inference_ms,
        })

    def summary(group):
        rr_mean = mean(row["rr_score"] for row in group)
        benefit_mean = mean(row["benefit_score"] for row in group)
        return {
            "samples": len(group), "mean_rr_score": rr_mean,
            "mean_direct_srtf_score": mean(row["direct_srtf_score"] for row in group),
            "mean_benefit_score": benefit_mean,
            "mean_continuation_oracle_score": mean(row["continuation_oracle_score"] for row in group),
            "relative_improvement_vs_rr": (rr_mean - benefit_mean) / rr_mean if rr_mean else 0.0,
            "switch_rate": mean(row["selected"] == "SRTF" for row in group),
            "false_switches": sum(row["false_switch"] for row in group),
            "missed_srtf_opportunities": sum(row["missed_srtf_opportunity"] for row in group),
            "remaining_oracle_headroom": benefit_mean - mean(row["continuation_oracle_score"] for row in group),
            "mean_inference_ms": mean(row["inference_ms"] for row in group),
        }

    overall = summary(rows)
    paired = paired_bootstrap_ci([row["difference_vs_rr"] for row in rows], bootstrap_samples, bootstrap_seed)
    overall.update({
        "seed": seed, "config": config.__dict__, "paired_difference_vs_rr": paired,
        "score_improvement_gate": overall["relative_improvement_vs_rr"] >= 0.01,
        "confidence_gate": paired["ci_high"] < 0,
        "decision_p99_ms": percentile([row["inference_ms"] for row in rows], 0.99),
    })
    overall["latency_gate"] = overall["decision_p99_ms"] < 10.0
    overall["eligible"] = all(overall[key] for key in ("score_improvement_gate", "confidence_gate", "latency_gate"))
    overall["recommended_policy"] = "Benefit selector" if overall["eligible"] else "Round Robin"
    overall["per_profile"] = {}
    for profile in PROFILES:
        group = [row for row in rows if row["profile"] == profile]
        profile_summary = summary(group)
        profile_summary["paired_difference_vs_rr"] = paired_bootstrap_ci(
            [row["difference_vs_rr"] for row in group], bootstrap_samples, bootstrap_seed
        )
        overall["per_profile"][profile] = profile_summary
    return rows, overall


def run_benefit_latency(
    model, config: BenefitConfig, samples_per_profile: int = 20, seed: int = 5050, warmups: int = 5
) -> tuple[list[dict], dict]:
    if samples_per_profile <= 0 or warmups < 0:
        raise ValueError("samples_per_profile must be positive and warmups must be non-negative")
    measurements = {size: [] for size in BENEFIT_SIZES}
    for size_index, (size, count) in enumerate(BENEFIT_SIZES.items()):
        for profile_index, profile in enumerate(PROFILES):
            for sample in range(samples_per_profile + warmups):
                workload = generate_workload(
                    profile, seed * 10_000_000 + size_index * 1_000_000 + profile_index * 100_000 + sample, count
                )
                state = _observe(workload.processes, config)
                if not (state.pending or state.ready or state.blocked):
                    continue
                started = perf_counter_ns()
                features = extract_observed_features(state)
                model.predict([[features[name] for name in BENEFIT_FEATURE_NAMES]])
                elapsed = (perf_counter_ns() - started) / 1_000_000
                if sample >= warmups:
                    measurements[size].append(elapsed)
    latency = {
        size: {
            "samples": len(values), "p50_ms": percentile(values, 0.50),
            "p95_ms": percentile(values, 0.95), "p99_ms": percentile(values, 0.99),
        }
        for size, values in measurements.items()
    }
    rows = [{"size": size, **values, "passes_gate": values["p99_ms"] < 10.0} for size, values in latency.items()]
    return rows, {
        "seed": seed, "samples_per_profile": samples_per_profile, "warmups": warmups,
        "sizes": BENEFIT_SIZES, "latency": latency,
        "gate_p99_ms": 10.0, "passes_latency_gate": all(row["passes_gate"] for row in rows),
    }


def _plot_setup():
    cache = Path(".cache/matplotlib").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = os.environ["XDG_CACHE_HOME"] = str(cache)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def save_benefit_evaluation(rows: list[dict], summary: dict, output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "evaluation.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    plt = _plot_setup()
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.bar(("Tuned RR", "Direct SRTF", "Benefit", "Continuation oracle"), (
        summary["mean_rr_score"], summary["mean_direct_srtf_score"],
        summary["mean_benefit_score"], summary["mean_continuation_oracle_score"],
    ))
    axis.set_ylabel("Mean fixed-anchor score (lower is better)")
    figure.tight_layout(); figure.savefig(output / "scores.png"); plt.close(figure)


def save_benefit_latency(rows: list[dict], summary: dict, output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "latency.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    (output / "latency_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    plt = _plot_setup()
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.plot(list(BENEFIT_SIZES), [summary["latency"][size]["p99_ms"] for size in BENEFIT_SIZES], marker="o")
    axis.axhline(10.0, color="red", linestyle="--")
    axis.set_ylabel("P99 decision latency (ms)")
    figure.tight_layout(); figure.savefig(output / "latency.png"); plt.close(figure)
