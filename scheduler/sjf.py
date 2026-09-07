"""
scheduler/sjf.py
----------------
Shortest Job First (SJF) — non-preemptive scheduler.

At each scheduling decision only processes that have already arrived are
considered.  Among those, the one with the smallest burst_time is chosen.
Ties are broken by arrival_time first, then by pid (lexicographic) to ensure
a deterministic, consistent result.
"""

from typing import List, Tuple
import copy

from simulator.process import Process


def sjf(processes: List[Process]) -> Tuple[List[Process], List[Tuple[str, int, int]]]:
    """
    Run the non-preemptive SJF scheduling algorithm.

    Parameters
    ----------
    processes : List[Process]
        The set of processes to schedule.  Each process is *copied* internally
        so the originals are not mutated.

    Returns
    -------
    scheduled : List[Process]
        Copies of the input processes with start_time and completion_time set.
    timeline  : List[Tuple[str, int, int]]
        Gantt-chart entries as (pid, start, end) triples, in execution order.
    """
    procs = copy.deepcopy(processes)

    remaining = list(procs)   # processes not yet executed
    timeline: List[Tuple[str, int, int]] = []
    scheduled: List[Process] = []
    current_time = 0

    while remaining:
        # Collect all processes that have arrived by current_time.
        available = [p for p in remaining if p.arrival_time <= current_time]

        if not available:
            # CPU is idle — jump forward to the next arrival.
            current_time = min(p.arrival_time for p in remaining)
            continue

        # Pick shortest job; break ties by arrival_time then pid.
        chosen = min(available, key=lambda p: (p.burst_time, p.arrival_time, p.pid))

        chosen.start_time = current_time
        chosen.completion_time = current_time + chosen.burst_time
        chosen.remaining_time = 0

        timeline.append((chosen.pid, chosen.start_time, chosen.completion_time))
        current_time = chosen.completion_time

        remaining.remove(chosen)
        scheduled.append(chosen)

    return scheduled, timeline
