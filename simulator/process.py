"""
simulator/process.py
--------------------
Defines the Process data model used by all scheduling algorithms.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


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
    cpu_bursts: Tuple[int, ...] | None = None
    io_bursts: Tuple[int, ...] = ()
    remaining_time: int = field(init=False)
    start_time: int = field(default=-1, init=False)
    completion_time: int = field(default=-1, init=False)
    burst_index: int = field(default=0, init=False)
    post_io_response_times: List[int] = field(default_factory=list, init=False)

    def __post_init__(self):
        if not self.pid:
            raise ValueError("pid must not be empty")
        if self.arrival_time < 0:
            raise ValueError("arrival_time must be non-negative")
        if self.burst_time <= 0:
            raise ValueError("burst_time must be positive")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")

        self.cpu_bursts = tuple(self.cpu_bursts or (self.burst_time,))
        self.io_bursts = tuple(self.io_bursts)
        if any(burst <= 0 for burst in self.cpu_bursts):
            raise ValueError("CPU bursts must be positive")
        if any(burst <= 0 for burst in self.io_bursts):
            raise ValueError("I/O bursts must be positive")
        if len(self.io_bursts) != len(self.cpu_bursts) - 1:
            raise ValueError("I/O bursts must occur between CPU bursts")
        if sum(self.cpu_bursts) != self.burst_time:
            raise ValueError("burst_time must equal the sum of CPU bursts")
        self.remaining_time = self.cpu_bursts[0]

    @property
    def total_io_time(self) -> int:
        return sum(self.io_bursts)

    def reset(self):
        """Re-initialise mutable scheduling fields so the same Process object
        can be reused across multiple algorithm runs."""
        self.start_time = -1
        self.completion_time = -1
        self.burst_index = 0
        self.remaining_time = self.cpu_bursts[0]
        self.post_io_response_times.clear()
