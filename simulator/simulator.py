"""
simulator/simulator.py
----------------------
Common simulation layer: computes per-process metrics from the output of any
scheduling algorithm and aggregates them into averages.

Metrics computed
----------------
* Completion Time  — set by the scheduler
* Turnaround Time  = Completion Time  - Arrival Time
* Waiting Time     = Turnaround Time  - Burst Time
* Response Time    = First Start Time - Arrival Time
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from simulator.process import Process


@dataclass
class ProcessMetrics:
    """Per-process scheduling metrics."""
    pid: str
    arrival_time: int
    burst_time: int
    priority: int
    start_time: int
    completion_time: int
    turnaround_time: int
    waiting_time: int
    response_time: int
    post_io_response_times: Tuple[int, ...]


@dataclass
class SimulationResult:
    """Aggregated result returned by run_simulation()."""
    algorithm: str
    process_metrics: List[ProcessMetrics]
    timeline: List[Tuple[str, int, int]]
    avg_turnaround_time: float
    avg_waiting_time: float
    avg_response_time: float
    cpu_utilization: float
    throughput: float
    makespan: int
    idle_time: int
    context_switches: int
    context_switch_time: int
    max_waiting_time: int


def compute_metrics(scheduled: List[Process]) -> List[ProcessMetrics]:
    """
    Derive per-process metrics from a list of scheduled (completed) processes.

    Parameters
    ----------
    scheduled : List[Process]
        Processes whose start_time and completion_time have been filled in by
        the scheduling algorithm.

    Returns
    -------
    List[ProcessMetrics]
        One ProcessMetrics entry per process.
    """
    metrics = []
    for p in scheduled:
        turnaround = p.completion_time - p.arrival_time
        waiting    = turnaround - p.burst_time - p.total_io_time
        response   = p.start_time - p.arrival_time
        metrics.append(ProcessMetrics(
            pid             = p.pid,
            arrival_time    = p.arrival_time,
            burst_time      = p.burst_time,
            priority        = p.priority,
            start_time      = p.start_time,
            completion_time = p.completion_time,
            turnaround_time = turnaround,
            waiting_time    = waiting,
            response_time   = response,
            post_io_response_times=tuple(p.post_io_response_times),
        ))
    return metrics


def run_simulation(
    algorithm_name: str,
    scheduler_fn,
    processes: List[Process],
    **kwargs,
) -> SimulationResult:
    """
    Execute a scheduling algorithm and return a SimulationResult.

    Parameters
    ----------
    algorithm_name : str
        Human-readable label (e.g. "FCFS", "Round Robin (q=2)").
    scheduler_fn   : callable
        A scheduling function with signature:
            scheduler_fn(processes, **kwargs) -> (scheduled, timeline)
    processes      : List[Process]
        Input processes (not mutated — the scheduler works on copies).
    **kwargs       : Any extra keyword arguments forwarded to scheduler_fn
        (e.g. quantum=2 for Round Robin).

    Returns
    -------
    SimulationResult
    """
    scheduled, timeline = scheduler_fn(processes, **kwargs)

    metrics = compute_metrics(scheduled)

    n = len(metrics)
    avg_tat = sum(m.turnaround_time for m in metrics) / n if n else 0.0
    avg_wt  = sum(m.waiting_time    for m in metrics) / n if n else 0.0
    avg_rt  = sum(m.response_time   for m in metrics) / n if n else 0.0
    busy_time = sum(end - start for pid, start, end in timeline if pid != "CS")
    context_switch_time = sum(end - start for pid, start, end in timeline if pid == "CS")
    makespan = max((end for _, _, end in timeline), default=0)
    process_timeline = [entry for entry in timeline if entry[0] != "CS"]
    context_switches = sum(
        previous[0] != current[0]
        for previous, current in zip(process_timeline, process_timeline[1:])
    )

    return SimulationResult(
        algorithm          = algorithm_name,
        process_metrics    = metrics,
        timeline           = timeline,
        avg_turnaround_time= avg_tat,
        avg_waiting_time   = avg_wt,
        avg_response_time  = avg_rt,
        cpu_utilization    = busy_time / makespan if makespan else 0.0,
        throughput         = n / makespan if makespan else 0.0,
        makespan           = makespan,
        idle_time          = makespan - busy_time - context_switch_time,
        context_switches   = context_switches,
        context_switch_time= context_switch_time,
        max_waiting_time   = max((metric.waiting_time for metric in metrics), default=0),
    )
