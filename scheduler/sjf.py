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

from simulator.process import Process
from simulator.engine import simulate


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
    return simulate(processes, "sjf")
