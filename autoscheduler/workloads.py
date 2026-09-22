"""Seeded synthetic workloads for scheduler experiments."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Tuple

from simulator.process import Process


PROFILES = ("interactive", "batch", "cpu_intensive", "io_intensive", "mixed")


@dataclass
class Workload:
    profile: str
    seed: int
    processes: Tuple[Process, ...]


_SETTINGS = {
    "interactive": (12, (0, 2), (2, 5), (1, 4), (2, 8)),
    "batch": (10, (0, 1), (1, 2), (8, 20), (2, 5)),
    "cpu_intensive": (8, (0, 2), (1, 2), (12, 30), (1, 3)),
    "io_intensive": (12, (0, 2), (3, 6), (1, 4), (4, 12)),
}


def generate_workload(
    profile: str,
    seed: int,
    process_count: int | None = None,
) -> Workload:
    """Generate one deterministic workload."""
    if profile not in PROFILES:
        raise ValueError(f"unknown workload profile: {profile}")
    if process_count is not None and process_count <= 0:
        raise ValueError("process_count must be positive")

    randomizer = random.Random(seed)
    count = process_count or (_SETTINGS[profile][0] if profile != "mixed" else 12)
    arrival = 0
    processes = []

    for index in range(count):
        process_profile = profile
        if profile == "mixed":
            process_profile = randomizer.choice(tuple(_SETTINGS))
        _, arrival_range, burst_count_range, cpu_range, io_range = _SETTINGS[process_profile]
        if index:
            arrival += randomizer.randint(*arrival_range)

        burst_count = randomizer.randint(*burst_count_range)
        cpu_bursts = tuple(randomizer.randint(*cpu_range) for _ in range(burst_count))
        io_bursts = tuple(randomizer.randint(*io_range) for _ in range(burst_count - 1))
        processes.append(
            Process(
                pid=f"P{index + 1}",
                arrival_time=arrival,
                burst_time=sum(cpu_bursts),
                priority=randomizer.randint(1, 5),
                cpu_bursts=cpu_bursts,
                io_bursts=io_bursts,
            )
        )

    return Workload(profile, seed, tuple(processes))
