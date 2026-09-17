"""Report-only fairness metrics for completed process samples."""

from __future__ import annotations

from statistics import mean, quantiles

from simulator.simulator import ProcessMetrics


FAIRNESS_FIELDS = (
    "max_waiting_time",
    "p95_waiting_time",
    "starvation_count",
    "priority_mean_waiting_time",
    "priority_max_waiting_time",
    "post_io_mean_response_time",
    "post_io_max_response_time",
)


def _mean_or_none(values: list[int]) -> float | None:
    return mean(values) if values else None


def aggregate_fairness(metrics: list[ProcessMetrics]) -> dict[str, float | int | None]:
    """Aggregate pooled process fairness metrics without affecting scheduler scores."""
    waits = [item.waiting_time for item in metrics]
    priority_waits = [item.waiting_time for item in metrics if item.priority in {1, 2}]
    io_responses = [delay for item in metrics for delay in item.post_io_response_times]
    return {
        "max_waiting_time": max(waits, default=0),
        "p95_waiting_time": quantiles(waits, n=100, method="inclusive")[94] if len(waits) > 1 else (waits[0] if waits else 0),
        "starvation_count": sum(item.waiting_time > 3 * item.burst_time for item in metrics),
        "priority_mean_waiting_time": _mean_or_none(priority_waits),
        "priority_max_waiting_time": max(priority_waits) if priority_waits else None,
        "post_io_mean_response_time": _mean_or_none(io_responses),
        "post_io_max_response_time": max(io_responses) if io_responses else None,
    }
