"""Preemptive priority scheduling with aging and an I/O-return boost."""

from typing import List, Tuple

from simulator.engine import simulate
from simulator.process import Process


def priority_round_robin(
    processes: List[Process],
    quantum: int = 2,
    aging_interval: int = 8,
    context_switch_cost: int = 1,
) -> Tuple[List[Process], List[Tuple[str, int, int]]]:
    """Run Priority Round Robin; lower priority numbers run first."""
    return simulate(
        processes,
        "priority_rr",
        quantum=quantum,
        aging_interval=aging_interval,
        context_switch_cost=context_switch_cost,
    )
