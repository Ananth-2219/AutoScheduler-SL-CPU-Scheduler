"""Canonical records for observed Linux and public workload traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


EVENT_TYPES = {
    "arrival", "wakeup", "switch_in", "switch_out", "block", "io_complete", "exit",
}


def validate_trace(trace: dict[str, Any]) -> None:
    for field in ("schema_version", "metadata", "events", "processes", "outcomes"):
        if field not in trace:
            raise ValueError(f"trace is missing {field}")

    trace_id = trace["metadata"].get("trace_id")
    if not trace_id:
        raise ValueError("trace metadata requires trace_id")
    if not trace["metadata"].get("source"):
        raise ValueError(f"{trace_id}: trace metadata requires source")

    previous_timestamp = -1
    for event in trace["events"]:
        timestamp = event.get("timestamp_ns")
        if not isinstance(timestamp, int) or timestamp < previous_timestamp:
            raise ValueError(f"{trace_id}: event timestamps must be monotonic non-negative integers")
        previous_timestamp = timestamp
        if event.get("type") not in EVENT_TYPES:
            raise ValueError(f"{trace_id}: unknown event type {event.get('type')!r}")

    seen_pids: set[int] = set()
    trace_truncated = bool(trace["metadata"].get("truncated"))
    for process in trace["processes"]:
        pid = process.get("pid")
        if not isinstance(pid, int) or pid < 0 or pid in seen_pids:
            raise ValueError(f"{trace_id}: process IDs must be unique non-negative integers")
        seen_pids.add(pid)
        arrival = process.get("arrival_ns")
        completion = process.get("completion_ns")
        if not isinstance(arrival, int) or arrival < 0:
            raise ValueError(f"{trace_id}: process {pid} has invalid arrival")
        if completion is None:
            if not (trace_truncated or process.get("truncated")):
                raise ValueError(f"{trace_id}: process {pid} has no completion and is not truncated")
        elif not isinstance(completion, int) or completion < arrival:
            raise ValueError(f"{trace_id}: process {pid} completes before arrival")


def read_traces(path: str | Path) -> list[dict[str, Any]]:
    traces = []
    with Path(path).open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                trace = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from error
            validate_trace(trace)
            traces.append(trace)
    return traces


def write_traces(traces: Iterable[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for trace in traces:
            validate_trace(trace)
            file.write(json.dumps(trace, separators=(",", ":"), ensure_ascii=True) + "\n")
