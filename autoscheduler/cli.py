"""Command-line interface for training and evaluating AutoScheduler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoscheduler.adaptive import run_adaptive
from autoscheduler.dataset import build_dataset, save_dataset
from autoscheduler.dynamic import (
    DYNAMIC_FEATURE_NAMES,
    DynamicRouterConfig,
    build_dynamic_dataset,
    evaluate_dynamic,
    save_dynamic_evaluation,
    tune_dynamic_config,
)
from autoscheduler.evaluation import compare_algorithms, score_results
from autoscheduler.experiments import evaluate_model, save_evaluation
from autoscheduler.latency import run_latency_experiment, save_latency
from autoscheduler.model import load_model, load_model_metadata, train_model
from autoscheduler.priority_rr import tune_priority_rr
from autoscheduler.workloads import PROFILES, generate_workload


DEFAULT_MODEL = Path("artifacts/model.joblib")
DEFAULT_DYNAMIC_MODEL = Path("artifacts/dynamic_model.joblib")


def _model(path: str):
    if not Path(path).exists():
        raise SystemExit(f"Model not found: {path}. Run `python main.py train` first.")
    return load_model(path)


def _train(arguments) -> None:
    tuning = tune_priority_rr(arguments.samples_per_profile, arguments.seed)
    priority_rr_config = {
        key: tuning["selected"][key]
        for key in ("quantum", "aging_interval", "context_switch_cost")
    }
    rows = build_dataset(arguments.samples_per_profile, arguments.seed, priority_rr_config)
    save_dataset(rows, arguments.dataset)
    report = train_model(rows, arguments.model, arguments.seed, priority_rr_config)
    report["priority_rr_tuning"] = tuning
    report_path = Path(arguments.model).with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Training rows: {report['rows']}")
    print(f"Validation accuracy: {report['validation_accuracy']:.3f}")
    print(f"Validation regret: {report['validation_mean_regret']:.4f}")
    print(f"Test accuracy: {report['test_accuracy']:.3f}")
    print(f"Test regret: {report['test_mean_regret']:.4f}")
    print(f"Model: {arguments.model}")


def _compare(arguments) -> None:
    workload = generate_workload(arguments.profile, arguments.seed, arguments.process_count)
    model = _model(arguments.model)
    config = load_model_metadata(arguments.model).get("priority_rr_config")
    results = compare_algorithms(workload.processes, config)
    scores = score_results(results)
    adaptive = run_adaptive(workload.processes, model, config)

    print(f"Workload: {workload.profile} | seed={workload.seed} | processes={len(workload.processes)}")
    print("Features:")
    for name, value in adaptive.features.items():
        print(f"  {name}: {value:.4f}")
    print("\nAlgorithm       Wait    Response  Turnaround  CPU utilization  Throughput  Score")
    for name, result in results.items():
        print(
            f"{name:<15} {result.avg_waiting_time:>7.2f} {result.avg_response_time:>9.2f} "
            f"{result.avg_turnaround_time:>11.2f} {result.cpu_utilization:>16.3f} "
            f"{result.throughput:>11.3f} {scores[name]:>6.3f}"
        )
    print(f"\nAdaptive selected: {adaptive.selected_algorithm} ({adaptive.inference_ms:.4f} ms)")
    print("Timeline:", " | ".join(f"{pid}[{start}-{end}]" for pid, start, end in adaptive.simulation.timeline))


def _evaluate(arguments) -> None:
    tuning = None
    metadata = load_model_metadata(arguments.model)
    priority_rr_config = metadata.get("priority_rr_config")
    if arguments.tune_priority_rr:
        if priority_rr_config:
            raise SystemExit("Model already contains frozen Priority-RR configuration.")
        tuning = tune_priority_rr(arguments.tune_samples_per_profile, arguments.tune_seed)
        priority_rr_config = {
            key: tuning["selected"][key]
            for key in ("quantum", "aging_interval", "context_switch_cost")
        }
    rows, summary = evaluate_model(
        _model(arguments.model),
        arguments.samples_per_profile,
        arguments.seed,
        priority_rr_config,
        metadata.get("static_baseline"),
    )
    if tuning:
        summary["priority_rr_tuning"] = tuning
    save_evaluation(rows, summary, arguments.output)
    print(f"Samples: {summary['samples']}")
    print(f"Accuracy: {summary['accuracy']:.3f}")
    print(f"Mean regret: {summary['mean_regret']:.4f}")
    print(f"Best static: {summary['best_static_algorithm']}")
    print(f"Adaptive score: {summary['mean_adaptive_score']:.4f}")
    print(f"Constant SJF score: {summary['constant_sjf']['mean_score']:.4f}")
    print(f"Oracle score: {summary['mean_oracle_score']:.4f}")
    print(f"Adaptive beats best static: {summary['adaptive_beats_best_static']}")
    print(f"Adaptive beats SJF: {summary['adaptive_beats_sjf']}")
    print(f"Statistically beats static: {summary['adaptive_statistically_beats_static']}")
    print(f"Eligible for next adaptive phase: {summary['eligible_for_next_adaptive_phase']}")
    print(f"Priority RR config: {summary['priority_rr_config']}")
    print(f"Priority RR beats SJF: {summary['priority_rr_beats_sjf']}")
    print(f"Results: {arguments.output}")


def _latency(arguments) -> None:
    score_path = Path(arguments.score_summary)
    if not score_path.exists():
        raise SystemExit(f"Score summary not found: {score_path}. Run `python main.py evaluate` first.")
    score_summary = json.loads(score_path.read_text(encoding="utf-8"))
    rows, summary = run_latency_experiment(
        _model(arguments.model), score_summary, arguments.samples_per_profile, arguments.seed, arguments.warmups
    )
    save_latency(rows, summary, arguments.output)
    print(f"P99 gate: < {summary['gate_p99_ms']:.0f} ms")
    print(f"Best static passing gate: {summary['best_static_policy']}")
    print(f"Adaptive beats static: {summary['adaptive_beats_static']}")
    print(f"Recommended policy: {summary['recommended_policy']}")
    print(f"Results: {arguments.output}")


def _dynamic_train(arguments) -> None:
    tuning = tune_dynamic_config(arguments.tuning_traces, arguments.seed)
    config = DynamicRouterConfig(**tuning["selected"])
    rows = build_dynamic_dataset(arguments.traces, arguments.seed, config)
    save_dataset(rows, arguments.dataset)
    report = train_model(
        rows, arguments.model, arguments.seed, feature_names=DYNAMIC_FEATURE_NAMES,
        metadata={"dynamic_config": config.__dict__, "dynamic_tuning": tuning},
    )
    report["dynamic_tuning"] = tuning
    Path(arguments.model).with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Dynamic rows: {report['rows']}")
    print(f"Router config: {config}")
    print(f"Model: {arguments.model}")


def _dynamic_evaluate(arguments) -> None:
    metadata = load_model_metadata(arguments.model)
    config = DynamicRouterConfig(**metadata.get("dynamic_config", {}))
    model = load_model(arguments.model, DYNAMIC_FEATURE_NAMES)
    rows, summary = evaluate_dynamic(model, arguments.traces, arguments.seed, config)
    save_dynamic_evaluation(rows, summary, arguments.output)
    print(f"P95 response gate: {summary['p95_response_gate']}")
    print(f"Weighted score gate: {summary['weighted_score_gate']}")
    print(f"Latency gate: {summary['latency_gate']}")
    print(f"Eligible: {summary['eligible']}")
    print(f"Results: {arguments.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adaptive CPU scheduling simulator")
    commands = parser.add_subparsers(dest="command", required=True)

    train = commands.add_parser("train", help="generate oracle labels and train a decision tree")
    train.add_argument("--samples-per-profile", type=int, default=500)
    train.add_argument("--seed", type=int, default=42)
    train.add_argument("--model", default=str(DEFAULT_MODEL))
    train.add_argument("--dataset", default="artifacts/training.csv")
    train.set_defaults(handler=_train)

    compare = commands.add_parser("compare", help="compare static and adaptive scheduling")
    compare.add_argument("--profile", choices=PROFILES, default="mixed")
    compare.add_argument("--seed", type=int, default=42)
    compare.add_argument("--process-count", type=int)
    compare.add_argument("--model", default=str(DEFAULT_MODEL))
    compare.set_defaults(handler=_compare)

    evaluate = commands.add_parser("evaluate", help="run held-out evaluation")
    evaluate.add_argument("--samples-per-profile", type=int, default=200)
    evaluate.add_argument("--seed", type=int, default=2026)
    evaluate.add_argument("--model", default=str(DEFAULT_MODEL))
    evaluate.add_argument("--output", default="results")
    evaluate.add_argument("--tune-priority-rr", action="store_true")
    evaluate.add_argument("--tune-samples-per-profile", type=int, default=500)
    evaluate.add_argument("--tune-seed", type=int, default=42)
    evaluate.set_defaults(handler=_evaluate)

    latency = commands.add_parser("latency", help="benchmark scheduler decision latency")
    latency.add_argument("--samples-per-profile", type=int, default=20)
    latency.add_argument("--warmups", type=int, default=5)
    latency.add_argument("--seed", type=int, default=3030)
    latency.add_argument("--model", default=str(DEFAULT_MODEL))
    latency.add_argument("--score-summary", default="results/summary.json")
    latency.add_argument("--output", default="results")
    latency.set_defaults(handler=_latency)

    dynamic_train = commands.add_parser("dynamic-train", help="tune and train safe epoch router")
    dynamic_train.add_argument("--traces", type=int, default=100)
    dynamic_train.add_argument("--tuning-traces", type=int, default=20)
    dynamic_train.add_argument("--seed", type=int, default=42)
    dynamic_train.add_argument("--model", default=str(DEFAULT_DYNAMIC_MODEL))
    dynamic_train.add_argument("--dataset", default="artifacts/dynamic_training.csv")
    dynamic_train.set_defaults(handler=_dynamic_train)

    dynamic_evaluate = commands.add_parser("dynamic-evaluate", help="evaluate safe epoch router")
    dynamic_evaluate.add_argument("--traces", type=int, default=1_000)
    dynamic_evaluate.add_argument("--seed", type=int, default=2026)
    dynamic_evaluate.add_argument("--model", default=str(DEFAULT_DYNAMIC_MODEL))
    dynamic_evaluate.add_argument("--output", default="results/dynamic")
    dynamic_evaluate.set_defaults(handler=_dynamic_evaluate)
    return parser


def main(argv=None) -> None:
    arguments = build_parser().parse_args(argv)
    arguments.handler(arguments)
