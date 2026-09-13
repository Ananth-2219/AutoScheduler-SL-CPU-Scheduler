"""Static scheduler comparison and oracle labeling."""

from __future__ import annotations

from typing import Iterable

from scheduler.fcfs import fcfs
from scheduler.priority import priority_scheduling
from scheduler.round_robin import round_robin
from scheduler.sjf import sjf
from simulator.process import Process
from simulator.simulator import SimulationResult, run_simulation


ALGORITHMS = {
    "FCFS": (fcfs, {}),
    "SJF": (sjf, {}),
    "Round Robin": (round_robin, {"quantum": 2}),
    "Priority": (priority_scheduling, {}),
}

SCORE_WEIGHTS = {
    "avg_waiting_time": 0.30,
    "avg_response_time": 0.25,
    "avg_turnaround_time": 0.20,
    "cpu_utilization": 0.15,
    "throughput": 0.10,
}


def run_algorithm(name: str, processes: Iterable[Process]) -> SimulationResult:
    scheduler, kwargs = ALGORITHMS[name]
    return run_simulation(name, scheduler, list(processes), **kwargs)


def compare_algorithms(processes: Iterable[Process]) -> dict[str, SimulationResult]:
    processes = list(processes)
    return {name: run_algorithm(name, processes) for name in ALGORITHMS}


def _normalize(values: dict[str, float], maximize: bool = False) -> dict[str, float]:
    low, high = min(values.values()), max(values.values())
    if high == low:
        return {name: 0.0 for name in values}
    if maximize:
        return {name: (high - value) / (high - low) for name, value in values.items()}
    return {name: (value - low) / (high - low) for name, value in values.items()}


def score_results(results: dict[str, SimulationResult]) -> dict[str, float]:
    """Return lower-is-better weighted scores normalized within one workload."""
    scores = dict.fromkeys(results, 0.0)
    for metric, weight in SCORE_WEIGHTS.items():
        values = {name: getattr(result, metric) for name, result in results.items()}
        normalized = _normalize(values, maximize=metric in {"cpu_utilization", "throughput"})
        for name, value in normalized.items():
            scores[name] += weight * value
    return scores


def oracle_label(results: dict[str, SimulationResult]) -> tuple[str, dict[str, float]]:
    scores = score_results(results)
    label = min(ALGORITHMS, key=lambda name: (scores[name], tuple(ALGORITHMS).index(name)))
    return label, scores
