"""Observed-only feature rows derived from canonical Linux traces."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Iterable


FEATURE_NAMES = (
    "arrivals_seen", "ready_count", "blocked_count", "running_count", "wait_mean_ms",
    "wait_p95_ms", "observed_service_mean_ms", "observed_service_variance_ms2",
    "completed_burst_mean_ms", "completed_burst_variance_ms2", "io_returns",
    "priority_mean", "priority_variance", "context_switches", "wakeups", "cpu_busy_fraction",
)
IDENTIFIER_NAMES = (
    "trace_id", "application", "workload_family", "scenario", "configuration_id",
    "capture_session", "decision_timestamp_ns",
)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: list[float]) -> float:
    mean = _mean(values)
    return _mean([(value - mean) ** 2 for value in values])


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    return sorted(values)[math.ceil(len(values) * 0.95) - 1]


def _busy_fraction(intervals: list[tuple[int, int, int | None]], start: int, end: int) -> float:
    by_cpu: dict[int | None, list[tuple[int, int]]] = {}
    for interval_start, interval_end, cpu in intervals:
        clipped_start, clipped_end = max(start, interval_start), min(end, interval_end)
        if clipped_start < clipped_end:
            by_cpu.setdefault(cpu, []).append((clipped_start, clipped_end))
    busy = 0
    for ranges in by_cpu.values():
        current_start, current_end = sorted(ranges)[0]
        for interval_start, interval_end in sorted(ranges)[1:]:
            if interval_start <= current_end:
                current_end = max(current_end, interval_end)
            else:
                busy += current_end - current_start
                current_start, current_end = interval_start, interval_end
        busy += current_end - current_start
    capacity = (end - start) * max(1, len(by_cpu))
    return busy / capacity if capacity else 0.0


def extract_features_at(trace: dict[str, Any], decision_timestamp_ns: int, feature_window_ms: int) -> dict[str, float]:
    """Return one feature vector using events strictly before the decision time."""
    window_start = decision_timestamp_ns - feature_window_ms * 1_000_000
    states: dict[int, str] = {}
    priorities: dict[int, int] = {}
    ready_since: dict[int, int] = {}
    running_since: dict[int, tuple[int, int | None]] = {}
    wait_samples: list[float] = []
    service_samples: list[float] = []
    completed_bursts: list[float] = []
    intervals: list[tuple[int, int, int | None]] = []
    arrivals_seen = wakeups = context_switches = io_returns = 0

    for item in trace["events"]:
        timestamp = item["timestamp_ns"]
        if timestamp >= decision_timestamp_ns:
            break
        pid, event_type, cpu = item["pid"], item["type"], item.get("cpu")
        if item.get("priority") is not None:
            priorities[pid] = item["priority"]
        in_window = timestamp >= window_start
        if event_type == "arrival":
            states[pid] = "ready"
            ready_since[pid] = timestamp
            arrivals_seen += int(in_window)
        elif event_type == "wakeup":
            io_returns += int(in_window and states.get(pid) == "blocked")
            states[pid] = "ready"
            ready_since[pid] = timestamp
            wakeups += int(in_window)
        elif event_type == "switch_in":
            if pid in ready_since:
                wait = (timestamp - ready_since.pop(pid)) / 1_000_000
                if in_window:
                    wait_samples.append(wait)
            states[pid] = "running"
            running_since[pid] = (timestamp, cpu)
            context_switches += int(in_window)
        elif event_type == "switch_out":
            started = running_since.pop(pid, None)
            if started:
                started_at, started_cpu = started
                service = (timestamp - started_at) / 1_000_000
                intervals.append((started_at, timestamp, started_cpu))
                if in_window:
                    service_samples.append(service)
                    if not str(item.get("previous_state") or "").startswith("R"):
                        completed_bursts.append(service)
            if str(item.get("previous_state") or "").startswith("R"):
                states[pid] = "ready"
                ready_since[pid] = timestamp
            else:
                states[pid] = "blocked"
        elif event_type == "block":
            states[pid] = "blocked"
        elif event_type == "exit":
            started = running_since.pop(pid, None)
            if started:
                intervals.append((started[0], timestamp, started[1]))
            states[pid] = "completed"
            ready_since.pop(pid, None)

    for started_at, cpu in running_since.values():
        intervals.append((started_at, decision_timestamp_ns, cpu))
    active_priorities = [priorities[pid] for pid, state in states.items()
                         if state != "completed" and pid in priorities]
    return {
        "arrivals_seen": float(arrivals_seen),
        "ready_count": float(sum(state == "ready" for state in states.values())),
        "blocked_count": float(sum(state == "blocked" for state in states.values())),
        "running_count": float(sum(state == "running" for state in states.values())),
        "wait_mean_ms": _mean(wait_samples),
        "wait_p95_ms": _p95(wait_samples),
        "observed_service_mean_ms": _mean(service_samples),
        "observed_service_variance_ms2": _variance(service_samples),
        "completed_burst_mean_ms": _mean(completed_bursts),
        "completed_burst_variance_ms2": _variance(completed_bursts),
        "io_returns": float(io_returns),
        "priority_mean": _mean(active_priorities),
        "priority_variance": _variance(active_priorities),
        "context_switches": float(context_switches),
        "wakeups": float(wakeups),
        "cpu_busy_fraction": _busy_fraction(intervals, window_start, decision_timestamp_ns),
    }


def extract_feature_rows(
    traces: Iterable[dict[str, Any]], initial_observation_ms: int, feature_window_ms: int,
    decision_interval_ms: int,
) -> list[dict[str, Any]]:
    rows = []
    for trace in traces:
        events = trace["events"]
        if not events:
            continue
        first, last = events[0]["timestamp_ns"], events[-1]["timestamp_ns"]
        step = decision_interval_ms * 1_000_000
        decision = first + initial_observation_ms * 1_000_000
        trace_id = trace["metadata"]["trace_id"]
        while decision <= last:
            rows.append({
                "trace_id": trace_id,
                "application": trace["metadata"].get("application"),
                "workload_family": trace["metadata"].get("workload_family"),
                # Legacy imports lack configuration metadata; isolate the trace rather than leak rows.
                "scenario": trace["metadata"].get("scenario") or trace_id,
                "configuration_id": trace["metadata"].get("configuration_id") or trace_id,
                "capture_session": trace["metadata"].get("capture_session"),
                "decision_timestamp_ns": decision,
                **extract_features_at(trace, decision, feature_window_ms),
            })
            decision += step
    return rows


def write_feature_rows(rows: Iterable[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=[*IDENTIFIER_NAMES, *FEATURE_NAMES])
        writer.writeheader()
        writer.writerows(rows)
