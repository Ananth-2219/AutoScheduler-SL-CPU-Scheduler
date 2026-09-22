"""
scheduler/fcfs.py
-----------------
First Come First Serve (FCFS) — non-preemptive scheduler.

Processes are executed strictly in arrival-time order.
When the CPU is idle (no process has arrived yet), time advances to the
next arrival.
"""

from typing import List, Tuple

from simulator.process import Process
from simulator.engine import simulate


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
    return simulate(processes, "fcfs")
