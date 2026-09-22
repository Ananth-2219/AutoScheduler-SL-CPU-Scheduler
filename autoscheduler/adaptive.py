"""Adaptive algorithm selection and execution."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterable

from autoscheduler.evaluation import ALGORITHMS, run_algorithm
from autoscheduler.features import FEATURE_NAMES, extract_features
from simulator.process import Process
from simulator.simulator import SimulationResult


@dataclass
class AdaptiveResult:
    selected_algorithm: str
    features: dict[str, float]
    inference_ms: float
    simulation: SimulationResult


def select_scheduler(features: dict[str, float], model) -> str:
    prediction = str(model.predict([[features[name] for name in FEATURE_NAMES]])[0])
    if prediction not in ALGORITHMS:
        raise ValueError(f"model selected unknown algorithm: {prediction}")
    return prediction


def run_adaptive(
    processes: Iterable[Process], model, priority_rr_config: dict | None = None
) -> AdaptiveResult:
    processes = list(processes)
    features = extract_features(processes)
    started = perf_counter()
    selected = select_scheduler(features, model)
    inference_ms = (perf_counter() - started) * 1_000
    return AdaptiveResult(
        selected,
        features,
        inference_ms,
        run_algorithm(selected, processes, priority_rr_config),
    )
