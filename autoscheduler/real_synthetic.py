"""Deterministic synthetic canonical traces for development-only pipeline checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autoscheduler.workloads import PROFILES, generate_workload
from autoscheduler.real_traces import write_traces


TICK_NS = 100_000_000


def _event(timestamp_ns: int, pid: int, event_type: str, priority: int, previous_state: str | None = None) -> dict[str, Any]:
    return {
        "timestamp_ns": timestamp_ns, "cpu": 0, "pid": pid, "type": event_type,
        "priority": priority + 100, "previous_state": previous_state,
        "ready_count": None, "wakeup_source": None,
    }


def _trace(profile: str, repetition: int, seed: int, generator_seed: int) -> dict[str, Any]:
    workload = generate_workload(profile, seed)
    trace_id = f"synthetic-{profile}-{repetition:03d}"
    events, processes = [], []
    for index, process in enumerate(workload.processes, 1):
        current = process.arrival_time * TICK_NS
        events.append(_event(current, index, "arrival", process.priority))
        for burst_index, burst in enumerate(process.cpu_bursts):
            events.append(_event(current, index, "switch_in", process.priority))
            current += burst * TICK_NS
            final = burst_index == len(process.cpu_bursts) - 1
            events.append(_event(current, index, "switch_out", process.priority, "Z" if final else "S"))
            if not final:
                current += process.io_bursts[burst_index] * TICK_NS
                events.append(_event(current, index, "wakeup", process.priority))
        completion = current + 1
        events.append(_event(completion, index, "exit", process.priority))
        processes.append({
            "pid": index, "arrival_ns": process.arrival_time * TICK_NS, "completion_ns": completion,
            "priority": process.priority + 100, "parent_pid": None, "cgroup": None,
            "application_family": profile, "truncated": False,
        })
    events.sort(key=lambda item: (item["timestamp_ns"], item["pid"], item["type"]))
    return {
        "schema_version": 1,
        "metadata": {
            "trace_id": trace_id, "source": "synthetic", "application": profile,
            "workload_family": profile, "scenario": f"{profile}-configuration",
            "configuration_id": f"{profile}-configuration", "capture_session": "synthetic-raw",
            "affinity_cpu": 0, "trace_cpus": "0", "generation_seed": generator_seed, "anonymized": False, "truncated": False,
        },
        "events": events, "processes": processes, "outcomes": [],
    }


def build_synthetic_traces(repetitions: int = 60, seed: int = 9001) -> list[dict[str, Any]]:
    """Create trace-shaped development data; it must never support a real ML claim."""
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")
    return [
        _trace(profile, repetition, seed + profile_index * 10_000 + repetition, seed)
        for profile_index, profile in enumerate(PROFILES)
        for repetition in range(repetitions)
    ]


def write_synthetic_traces(path: str | Path, repetitions: int = 60, seed: int = 9001) -> list[dict[str, Any]]:
    traces = build_synthetic_traces(repetitions, seed)
    write_traces(traces, path)
    return traces
