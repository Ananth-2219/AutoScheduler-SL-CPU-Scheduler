"""Shared single-CPU event simulation for all scheduling policies."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from simulator.process import Process


Timeline = List[Tuple[str, int, int]]


@dataclass
class _Ready:
    time: int
    sequence: int
    process: Process
    priority: int


def simulate(
    processes: Iterable[Process],
    policy: str,
    quantum: int | None = None,
    aging_interval: int | None = None,
    context_switch_cost: int = 0,
) -> tuple[List[Process], Timeline]:
    """Run a supported single-CPU policy with CPU/I/O bursts."""
    if policy in {"rr", "priority_rr"} and (quantum is None or quantum <= 0):
        raise ValueError("quantum must be positive")
    if policy == "priority_rr" and (aging_interval is None or aging_interval <= 0):
        raise ValueError("aging_interval must be positive")
    if context_switch_cost < 0:
        raise ValueError("context_switch_cost must be non-negative")

    # ponytail: list queues suit small synthetic workloads; use deque/heap for large traces.
    pending = sorted(copy.deepcopy(list(processes)), key=lambda p: (p.arrival_time, p.pid))
    if len({process.pid for process in pending}) != len(pending):
        raise ValueError("process IDs must be unique")
    for process in pending:
        process.reset()

    ready: List[_Ready] = []
    blocked: List[tuple[int, Process, int]] = []
    completed: List[Process] = []
    timeline: Timeline = []
    current_time = 0
    sequence = 0
    last_pid: str | None = None

    def release(until: int) -> None:
        nonlocal sequence
        events: List[tuple[int, str, Process, int]] = []
        while pending and pending[0].arrival_time <= until:
            process = pending.pop(0)
            events.append((process.arrival_time, process.pid, process, process.priority))
        still_blocked = []
        for wake_time, process, priority in blocked:
            if wake_time <= until:
                events.append((wake_time, process.pid, process, priority))
            else:
                still_blocked.append((wake_time, process, priority))
        blocked[:] = still_blocked
        for ready_time, _, process, priority in sorted(events, key=lambda event: (event[0], event[1])):
            ready.append(_Ready(ready_time, sequence, process, priority))
            sequence += 1

    def take_ready() -> _Ready:
        if policy == "rr":
            index = min(range(len(ready)), key=lambda i: ready[i].sequence)
        elif policy == "priority_rr":
            index = min(
                range(len(ready)),
                key=lambda i: (
                    max(1, ready[i].priority - (current_time - ready[i].time) // (aging_interval or 1)),
                    ready[i].sequence,
                ),
            )
        elif policy == "sjf":
            index = min(
                range(len(ready)),
                key=lambda i: (
                    ready[i].process.remaining_time,
                    ready[i].time,
                    ready[i].process.pid,
                ),
            )
        elif policy == "priority":
            index = min(
                range(len(ready)),
                key=lambda i: (
                    ready[i].process.priority,
                    ready[i].time,
                    ready[i].process.pid,
                ),
            )
        else:
            index = min(range(len(ready)), key=lambda i: (ready[i].time, ready[i].process.pid))
        return ready.pop(index)

    while pending or blocked or ready:
        release(current_time)
        if not ready:
            next_times = [process.arrival_time for process in pending]
            next_times.extend(wake_time for wake_time, _, _ in blocked)
            current_time = min(next_times)
            release(current_time)

        ready_process = take_ready()
        process = ready_process.process
        if last_pid is not None and last_pid != process.pid and context_switch_cost:
            timeline.append(("CS", current_time, current_time + context_switch_cost))
            current_time += context_switch_cost
            release(current_time)
        if process.start_time == -1:
            process.start_time = current_time

        run_for = process.remaining_time
        if policy in {"rr", "priority_rr"}:
            run_for = min(run_for, quantum or run_for)
        end_time = current_time + run_for
        timeline.append((process.pid, current_time, end_time))
        process.remaining_time -= run_for
        current_time = end_time
        last_pid = process.pid
        release(current_time)

        if process.remaining_time:
            ready.append(_Ready(current_time, sequence, process, process.priority))
            sequence += 1
            continue

        if process.burst_index < len(process.cpu_bursts) - 1:
            wake_time = current_time + process.io_bursts[process.burst_index]
            process.burst_index += 1
            process.remaining_time = process.cpu_bursts[process.burst_index]
            blocked.append((wake_time, process, max(1, process.priority - 1)))
            continue

        process.completion_time = current_time
        completed.append(process)

    return completed, timeline
