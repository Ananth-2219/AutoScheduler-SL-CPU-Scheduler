"""Pre-simulation workload feature extraction."""

from __future__ import annotations

from statistics import mean, pvariance
from typing import Iterable

from simulator.process import Process


FEATURE_NAMES = (
    "process_count",
    "arrival_rate",
    "burst_mean",
    "burst_variance",
    "short_job_ratio",
    "priority_mean",
    "priority_variance",
    "io_frequency",
    "io_cpu_ratio",
)


def extract_features(processes: Iterable[Process]) -> dict[str, float]:
    """Return ordered features available before scheduling starts."""
    processes = list(processes)
    if not processes:
        return dict.fromkeys(FEATURE_NAMES, 0.0)

    arrivals = [process.arrival_time for process in processes]
    cpu_totals = [process.burst_time for process in processes]
    priorities = [process.priority for process in processes]
    short_jobs = [mean(process.cpu_bursts) <= 4 for process in processes]
    total_cpu = sum(cpu_totals)
    total_io = sum(process.total_io_time for process in processes)
    arrival_span = max(arrivals) - min(arrivals) + 1

    return {
        "process_count": float(len(processes)),
        "arrival_rate": len(processes) / arrival_span,
        "burst_mean": mean(cpu_totals),
        "burst_variance": pvariance(cpu_totals),
        "short_job_ratio": sum(short_jobs) / len(processes),
        "priority_mean": mean(priorities),
        "priority_variance": pvariance(priorities),
        "io_frequency": mean(len(process.io_bursts) for process in processes),
        "io_cpu_ratio": total_io / total_cpu,
    }
