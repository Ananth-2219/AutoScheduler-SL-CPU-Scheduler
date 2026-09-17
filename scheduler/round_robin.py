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

from simulator.process import Process
from simulator.engine import simulate


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
    return simulate(processes, "rr", quantum)
