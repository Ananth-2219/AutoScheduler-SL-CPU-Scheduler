"""Command-line interface for training and evaluating AutoScheduler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoscheduler.adaptive import run_adaptive
from autoscheduler.dataset import build_dataset, save_dataset
from autoscheduler.evaluation import compare_algorithms, score_results
from autoscheduler.experiments import evaluate_model, save_evaluation
from autoscheduler.model import load_model, train_model
from autoscheduler.workloads import PROFILES, generate_workload


DEFAULT_MODEL = Path("artifacts/model.joblib")


def _model(path: str):
    if not Path(path).exists():
        raise SystemExit(f"Model not found: {path}. Run `python main.py train` first.")
    return load_model(path)


def _train(arguments) -> None:
    rows = build_dataset(arguments.samples_per_profile, arguments.seed)
    save_dataset(rows, arguments.dataset)
    report = train_model(rows, arguments.model, arguments.seed)
    report_path = Path(arguments.model).with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Training rows: {report['rows']}")
    print(f"Validation accuracy: {report['validation_accuracy']:.3f}")
    print(f"Test accuracy: {report['test_accuracy']:.3f}")
    print(f"Model: {arguments.model}")


def _compare(arguments) -> None:
    workload = generate_workload(arguments.profile, arguments.seed, arguments.process_count)
    model = _model(arguments.model)
    results = compare_algorithms(workload.processes)
    scores = score_results(results)
    adaptive = run_adaptive(workload.processes, model)

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
    rows, summary = evaluate_model(
        _model(arguments.model), arguments.samples_per_profile, arguments.seed
    )
    save_evaluation(rows, summary, arguments.output)
    print(f"Samples: {summary['samples']}")
    print(f"Accuracy: {summary['accuracy']:.3f}")
    print(f"Mean regret: {summary['mean_regret']:.4f}")
    print(f"Best static: {summary['best_static_algorithm']}")
    print(f"Adaptive score: {summary['mean_adaptive_score']:.4f}")
    print(f"Oracle score: {summary['mean_oracle_score']:.4f}")
    print(f"Adaptive beats best static: {summary['adaptive_beats_best_static']}")
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
    evaluate.set_defaults(handler=_evaluate)
    return parser


def main(argv=None) -> None:
    arguments = build_parser().parse_args(argv)
    arguments.handler(arguments)
