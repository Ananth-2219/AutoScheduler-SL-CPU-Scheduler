"""
scheduler/round_robin.py
------------------------
Round Robin (RR) — preemptive scheduler with a configurable time quantum.

Processes are served in FIFO order within the ready queue.  When a process
exhausts its time quantum without finishing, it is re-queued at the back.
New arrivals that arrive during a quantum are added to the ready queue in
arrival-time order before the preempted process is re-queued.
"""

from typing import List, Tuple
import copy
from collections import deque

from simulator.process import Process


def round_robin(
    processes: List[Process],
    quantum: int = 2,
) -> Tuple[List[Process], List[Tuple[str, int, int]]]:
    """
    Run the Round Robin scheduling algorithm.

    Parameters
    ----------
    processes : List[Process]
        The set of processes to schedule.  Each process is *copied* internally
        so the originals are not mutated.
    quantum   : int
        Time slice allocated to each process per turn (default 2).

    Returns
    -------
    scheduled : List[Process]
        Copies of the input processes with start_time and completion_time set,
        in the order they completed.
    timeline  : List[Tuple[str, int, int]]
        Gantt-chart entries as (pid, start, end) triples.  A process that runs
        multiple turns will have multiple entries.
    """
    procs = copy.deepcopy(processes)

    # Sort by arrival time so we can enqueue them in order of arrival.
    # Tie-break by pid for determinism.
    arrival_order = sorted(procs, key=lambda p: (p.arrival_time, p.pid))

    # Index into arrival_order — tracks which processes have been enqueued.
    next_arrival_idx = 0

    ready_queue: deque = deque()
    timeline: List[Tuple[str, int, int]] = []
    scheduled: List[Process] = []
    current_time = 0

    # Helper: enqueue all processes that have arrived by `t`.
    def enqueue_arrivals(t: int):
        nonlocal next_arrival_idx
        while next_arrival_idx < len(arrival_order):
            p = arrival_order[next_arrival_idx]
            if p.arrival_time <= t:
                ready_queue.append(p)
                next_arrival_idx += 1
            else:
                break

    # Seed the queue with processes available at time 0.
    enqueue_arrivals(current_time)

    while ready_queue or next_arrival_idx < len(arrival_order):
        if not ready_queue:
            # CPU idle — jump to the next arrival.
            current_time = arrival_order[next_arrival_idx].arrival_time
            enqueue_arrivals(current_time)
            continue

        proc = ready_queue.popleft()

        # Record start_time the first time this process gets the CPU.
        if proc.start_time == -1:
            proc.start_time = current_time

        # Run for at most `quantum` units.
        run_for = min(quantum, proc.remaining_time)
        start = current_time
        end = current_time + run_for
        timeline.append((proc.pid, start, end))

        proc.remaining_time -= run_for
        current_time = end

        # Enqueue any new arrivals that came in during this quantum
        # BEFORE re-queuing the current process (if it isn't done).
        enqueue_arrivals(current_time)

        if proc.remaining_time == 0:
            proc.completion_time = current_time
            scheduled.append(proc)
        else:
            # Process still has work left — put it at the back of the queue.
            ready_queue.append(proc)

    return scheduled, timeline
