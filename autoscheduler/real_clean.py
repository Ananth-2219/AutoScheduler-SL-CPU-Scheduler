"""Create shareable, anonymized copies of completed canonical traces."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from autoscheduler.real_traces import read_traces, write_traces


SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]+")


def _safe_identifier(value: Any, fallback: str | None = None) -> str | None:
    if isinstance(value, str) and SAFE_IDENTIFIER.fullmatch(value):
        return value
    return fallback


def _require_complete(trace: dict[str, Any]) -> None:
    metadata = trace["metadata"]
    if metadata.get("truncated") or any(
        process.get("truncated") or process.get("completion_ns") is None
        for process in trace["processes"]
    ):
        raise ValueError(f"{metadata['trace_id']}: incomplete traces cannot be anonymized")


def _clean_trace(
    trace: dict[str, Any], trace_id: str, capture_session: str
) -> dict[str, Any]:
    _require_complete(trace)
    metadata = trace["metadata"]
    family = _safe_identifier(metadata.get("workload_family"), "workload")
    pid_map = {process["pid"]: index for index, process in enumerate(trace["processes"], 1)}

    events = []
    for event in trace["events"]:
        event = event.copy()
        if event["pid"] not in pid_map:
            raise ValueError(f"{metadata['trace_id']}: event refers to an unknown process")
        event["pid"] = pid_map[event["pid"]]
        source = event.get("wakeup_source")
        event["wakeup_source"] = pid_map.get(source)
        events.append(event)

    processes = []
    for process in trace["processes"]:
        processes.append({
            "pid": pid_map[process["pid"]],
            "arrival_ns": process["arrival_ns"],
            "completion_ns": process["completion_ns"],
            "priority": process.get("priority"),
            "parent_pid": pid_map.get(process.get("parent_pid")),
            "cgroup": None,
            "application_family": family,
            "truncated": False,
        })

    return {
        "schema_version": trace["schema_version"],
        "metadata": {
            "trace_id": trace_id,
            "source": _safe_identifier(metadata.get("source"), "unknown"),
            "application": family,
            "workload_family": family,
            "scenario": _safe_identifier(metadata.get("scenario")),
            "configuration_id": _safe_identifier(metadata.get("configuration_id")),
            "capture_session": capture_session,
            "affinity_cpu": metadata.get("affinity_cpu")
            if isinstance(metadata.get("affinity_cpu"), int) else None,
            "trace_cpus": _safe_identifier(metadata.get("trace_cpus")),
            "generation_seed": metadata.get("generation_seed") if isinstance(metadata.get("generation_seed"), int) else None,
            "anonymized": True,
            "truncated": False,
        },
        "events": events,
        "processes": processes,
        "outcomes": [],
    }


def clean_traces(
    traces: Iterable[dict[str, Any]], capture_session: str
) -> list[dict[str, Any]]:
    """Return deterministic, anonymized copies; source traces are never mutated."""
    if not _safe_identifier(capture_session):
        raise ValueError("capture session must be a safe identifier")
    ordered = sorted(traces, key=lambda trace: trace["metadata"]["trace_id"])
    return [
        _clean_trace(trace, f"{capture_session}-trace-{index:04d}", capture_session)
        for index, trace in enumerate(ordered, 1)
    ]


def clean_trace_files(
    paths: Iterable[str | Path], output: str | Path, capture_session: str
) -> list[dict[str, Any]]:
    traces = [trace for path in paths for trace in read_traces(path)]
    cleaned = clean_traces(traces, capture_session)
    write_traces(cleaned, output)
    return cleaned
