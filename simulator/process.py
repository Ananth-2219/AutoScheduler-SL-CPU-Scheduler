"""
simulator/process.py
--------------------
Defines the Process data model used by all scheduling algorithms.
"""

from dataclasses import dataclass, field


@dataclass
class Process:
    """
    Represents a single process in the CPU scheduling simulation.

    Attributes:
        pid            : Unique process identifier (e.g. "P1").
        arrival_time   : Time at which the process arrives in the ready queue.
        burst_time     : Total CPU time required by the process.
        priority       : Scheduling priority (1 = highest priority).
        remaining_time : CPU time still needed; starts equal to burst_time.
        start_time     : Wall-clock time when the process first gets the CPU.
                         -1 means the process has not started yet.
        completion_time: Wall-clock time when the process finishes execution.
                         -1 means the process has not completed yet.
    """

    pid: str
    arrival_time: int
    burst_time: int
    priority: int = 0
    remaining_time: int = field(init=False)
    start_time: int = field(default=-1, init=False)
    completion_time: int = field(default=-1, init=False)

    def __post_init__(self):
        # remaining_time mirrors burst_time at creation time.
        self.remaining_time = self.burst_time

    def reset(self):
        """Re-initialise mutable scheduling fields so the same Process object
        can be reused across multiple algorithm runs."""
        self.remaining_time = self.burst_time
        self.start_time = -1
        self.completion_time = -1
