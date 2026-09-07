"""
scheduler/fcfs.py
-----------------
First Come First Serve (FCFS) — non-preemptive scheduler.

Processes are executed strictly in arrival-time order.
When the CPU is idle (no process has arrived yet), time advances to the
next arrival.
"""

from typing import List, Tuple
import copy

from simulator.process import Process


def fcfs(processes: List[Process]) -> Tuple[List[Process], List[Tuple[str, int, int]]]:
    """
    Run the FCFS scheduling algorithm.

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
    # Work on deep copies so the caller's objects are untouched.
    procs = copy.deepcopy(processes)

    # Sort by arrival time; break ties by pid (lexicographic) for consistency.
    procs.sort(key=lambda p: (p.arrival_time, p.pid))

    timeline: List[Tuple[str, int, int]] = []
    current_time = 0

    for proc in procs:
        # If the CPU is idle, advance time to when this process arrives.
        if current_time < proc.arrival_time:
            current_time = proc.arrival_time

        proc.start_time = current_time
        proc.completion_time = current_time + proc.burst_time
        proc.remaining_time = 0

        timeline.append((proc.pid, proc.start_time, proc.completion_time))
        current_time = proc.completion_time

    return procs, timeline
