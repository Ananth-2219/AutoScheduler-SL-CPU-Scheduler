"""Reconstruct single-CPU simulator workloads from completed Linux traces."""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import ceil
from pathlib import Path
from typing import Any

from simulator.process import Process


TICK_NS = 1_000_000


@dataclass
class ReplayWorkload:
    trace_id: str
    affinity_cpu: int
    processes: list[Process]
    rejected_processes: dict[int, str]


def _ticks(duration_ns: int) -> int:
    return max(1, ceil(duration_ns / TICK_NS))


def _is_io_block(previous_state: object) -> bool:
    state = str(previous_state or "")
    return bool(state) and not state.startswith(("R", "Z", "X"))


def _priority(value: object) -> int:
    return max(0, int(value or 0) - 100)


def _rebuild_process(
    trace_id: str, process_record: dict[str, Any], events: list[dict[str, Any]], origin_ns: int,
    affinity_cpu: int,
) -> Process | str:
    pid = process_record["pid"]
    if process_record.get("truncated") or process_record.get("completion_ns") is None:
        return "process_truncated"
    arrival_ns = process_record["arrival_ns"]
    all_process_events = [event for event in events if event["pid"] == pid]
    process_events = [event for event in all_process_events if event["timestamp_ns"] >= arrival_ns]
    if any(
        event["type"] in {"switch_in", "switch_out"} and event.get("cpu") != affinity_cpu
        for event in process_events
    ):
        return "migrated_cpu"
    if not any(event["type"] == "exit" for event in process_events):
        return "missing_exit_event"

    prior_switch = next(
        (
            event for event in reversed(all_process_events)
            if event["timestamp_ns"] < arrival_ns and event["type"] in {"switch_in", "switch_out"}
        ),
        None,
    )
    if prior_switch and prior_switch["type"] == "switch_in":
        if prior_switch.get("cpu") != affinity_cpu:
            return "migrated_cpu"
        running_at: int | None = arrival_ns
    else:
        running_at = None

    cpu_ns = 0
    cpu_bursts: list[int] = []
    io_bursts: list[int] = []
    blocked_at: int | None = None
    for event in process_events:
        timestamp, event_type = event["timestamp_ns"], event["type"]
        if event_type == "switch_in":
            if running_at is not None:
                return "duplicate_switch_in"
            running_at = timestamp
        elif event_type == "switch_out":
            if running_at is None:
                return "unmatched_switch_out"
            cpu_ns += timestamp - running_at
            running_at = None
            if _is_io_block(event.get("previous_state")):
                blocked_at = timestamp
        elif event_type == "wakeup" and blocked_at is not None:
            if cpu_ns <= 0:
                return "empty_cpu_burst"
            cpu_bursts.append(_ticks(cpu_ns))
            io_bursts.append(_ticks(timestamp - blocked_at))
            cpu_ns = 0
            blocked_at = None
        elif event_type == "exit":
            if running_at is not None:
                cpu_ns += timestamp - running_at
                running_at = None
            if blocked_at is not None:
                return "missing_wakeup_after_block"
            break

    if running_at is not None:
        return "unfinished_cpu_service"
    if blocked_at is not None:
        return "missing_wakeup_after_block"
    if cpu_ns <= 0:
        return "no_cpu_service"
    cpu_bursts.append(_ticks(cpu_ns))
    return Process(
        pid=f"{trace_id}:{pid}",
        arrival_time=ceil((arrival_ns - origin_ns) / TICK_NS),
        burst_time=sum(cpu_bursts),
        priority=_priority(process_record.get("priority")),
        cpu_bursts=tuple(cpu_bursts),
        io_bursts=tuple(io_bursts),
    )


def build_replay_workload(trace: dict[str, Any]) -> ReplayWorkload:
    """Build a replay workload; reject process data unsuitable for single-CPU replay."""
    if trace["metadata"].get("truncated"):
        raise ValueError(f"{trace['metadata']['trace_id']}: truncated traces cannot be replayed")
    events = sorted(trace["events"], key=lambda event: event["timestamp_ns"])
    if not events:
        raise ValueError(f"{trace['metadata']['trace_id']}: trace has no events")
    affinity_cpu = trace["metadata"].get("affinity_cpu", trace["metadata"].get("cpu"))
    if not isinstance(affinity_cpu, int):
        raise ValueError(f"{trace['metadata']['trace_id']}: affinity CPU is required")

    origin_ns = events[0]["timestamp_ns"]
    processes: list[Process] = []
    rejected: dict[int, str] = {}
    for process_record in sorted(trace["processes"], key=lambda item: item["pid"]):
        rebuilt = _rebuild_process(
            trace["metadata"]["trace_id"], process_record, events, origin_ns, affinity_cpu
        )
        if isinstance(rebuilt, str):
            rejected[process_record["pid"]] = rebuilt
        else:
            processes.append(rebuilt)
    if not processes:
        raise ValueError(f"{trace['metadata']['trace_id']}: no eligible processes for replay")
    return ReplayWorkload(trace["metadata"]["trace_id"], affinity_cpu, processes, rejected)


def _process_record(process: Process) -> dict[str, Any]:
    return {
        "pid": process.pid,
        "arrival_time": process.arrival_time,
        "burst_time": process.burst_time,
        "priority": process.priority,
        "cpu_bursts": list(process.cpu_bursts),
        "io_bursts": list(process.io_bursts),
    }


def build_replay_manifest(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Serialize eligible replay workloads and every explicit exclusion."""
    entries = []
    for trace in sorted(traces, key=lambda item: item["metadata"]["trace_id"]):
        trace_id = trace["metadata"]["trace_id"]
        try:
            replay = build_replay_workload(trace)
        except ValueError as error:
            entries.append({
                "trace_id": trace_id,
                "status": "rejected",
                "reason": str(error),
                "accepted_processes": 0,
                "rejected_processes": [],
                "processes": [],
            })
            continue
        entries.append({
            "trace_id": trace_id,
            "status": "accepted",
            "affinity_cpu": replay.affinity_cpu,
            "accepted_processes": len(replay.processes),
            "rejected_processes": [
                {"pid": pid, "reason": reason}
                for pid, reason in sorted(replay.rejected_processes.items())
            ],
            "processes": [_process_record(process) for process in replay.processes],
        })
    return {
        "schema_version": 1,
        "kind": "offline_replay",
        "traces": entries,
        "summary": {
            "accepted_traces": sum(entry["status"] == "accepted" for entry in entries),
            "rejected_traces": sum(entry["status"] == "rejected" for entry in entries),
            "accepted_processes": sum(entry["accepted_processes"] for entry in entries),
            "rejected_processes": sum(len(entry["rejected_processes"]) for entry in entries),
        },
    }


def write_replay_manifest(traces: list[dict[str, Any]], output_path: str | Path) -> dict[str, Any]:
    manifest = build_replay_manifest(traces)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
