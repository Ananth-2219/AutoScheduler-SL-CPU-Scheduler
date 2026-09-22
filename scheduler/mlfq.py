"""Three-level Multi-Level Feedback Queue scheduler."""

from typing import List, Tuple

from simulator.engine import simulate
from simulator.process import Process


def mlfq(
    processes: List[Process],
    quanta: tuple[int, ...] = (2, 4, 8),
    aging_threshold: int = 20,
    context_switch_cost: int = 0,
    decision_times_ns: list[int] | None = None,
) -> Tuple[List[Process], List[Tuple[str, int, int]]]:
    """Run fixed MLFQ with top-queue admission, feedback, and aging."""
    return simulate(
        processes,
        "mlfq",
        queue_quanta=quanta,
        aging_threshold=aging_threshold,
        context_switch_cost=context_switch_cost,
        decision_times_ns=decision_times_ns,
    )
