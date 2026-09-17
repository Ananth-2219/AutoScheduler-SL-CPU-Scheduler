"""
scheduler/priority.py
---------------------
Non-preemptive Priority Scheduling.

Convention: priority 1 = highest priority (lower number → runs first).

At each scheduling decision only processes that have already arrived are
considered.  Among those, the one with the lowest priority number is chosen.
Ties are broken by arrival_time first, then by pid (lexicographic) for a
deterministic, consistent result.
"""

from typing import List, Tuple

from simulator.process import Process
from simulator.engine import simulate


def priority_scheduling(
    processes: List[Process],
) -> Tuple[List[Process], List[Tuple[str, int, int]]]:
    """
    Run the non-preemptive Priority scheduling algorithm.

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
    return simulate(processes, "priority")
