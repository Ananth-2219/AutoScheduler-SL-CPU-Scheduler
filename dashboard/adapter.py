"""Bounded, read-only demo adapter around the existing simulator.

Replay frames derive CPU service and I/O intervals from returned timeline slices
and the tiny declared workloads. Ready membership is exposed, not internal queue
order. No scheduling decisions are made here or in the browser.
"""
from dataclasses import asdict
from functools import lru_cache
import json
from pathlib import Path

from autoscheduler.evaluation import ALGORITHMS, DEPLOYABLE_ALGORITHMS, SCORE_WEIGHTS, compare_algorithms, score_result_against_reference
from autoscheduler.features import extract_features
from autoscheduler.fairness import aggregate_fairness
from scheduler.mlfq import mlfq
from simulator.process import Process
from simulator.simulator import run_simulation

ROOT = Path(__file__).resolve().parents[1]
WORKLOADS = {
    "short_jobs": {"name": "Short-job-heavy", "description": "A long job meets a stream of short tasks. Compare responsiveness and completion order.",
                   "jobs": [(0, (12,), (), 3), (1, (2,), (), 1), (2, (1,), (), 2), (3, (3,), (), 1), (4, (2,), (), 2), (5, (1,), (), 1)]},
    "mixed_io": {"name": "Mixed CPU / I/O", "description": "Interactive tasks leave the CPU for I/O and return while CPU-bound jobs compete.",
                 "jobs": [(0, (2, 3, 2), (4, 3), 1), (0, (14,), (), 3), (1, (1, 2, 1), (5, 4), 2), (2, (7,), (), 2), (4, (2, 3), (3,), 1), (6, (3,), (), 3)]},
    "bursty": {"name": "Bursty arrivals", "description": "Two arrival bursts create changing queue pressure. Watch preemption and first service.",
               "jobs": [(0, (10,), (), 3), (0, (6,), (), 2), (1, (3,), (), 1), (8, (2,), (), 1), (8, (5,), (), 2), (9, (1,), (), 1), (14, (4,), (), 2), (14, (2,), (), 3)]},
}


def read_json(path):
    return json.loads((ROOT / path).read_text())


def processes(workload):
    if workload not in WORKLOADS:
        raise ValueError("Choose one of the three built-in demo workloads.")
    return [Process(f"P{i}", arrival, sum(cpu), priority, cpu_bursts=cpu, io_bursts=io)
            for i, (arrival, cpu, io, priority) in enumerate(WORKLOADS[workload]["jobs"], 1)]


def catalog():
    metadata_path = "artifacts/demo_tree.json"
    metadata = read_json(metadata_path) if (ROOT / metadata_path).exists() else None
    return {"workloads": [{"id": key, "name": value["name"], "description": value["description"], "count": len(value["jobs"])}
                          for key, value in WORKLOADS.items()],
        "algorithms": list(ALGORITHMS) + ["MLFQ", "Tuned MLFQ"], "score_weights": SCORE_WEIGHTS,
        "offline": {"source": metadata_path, "metadata": metadata, "inference_available": False,
            "message": "Verified saved metadata is available. The matching fitted six-policy binary is not available; live predictions are not fabricated."},
        "research": read_json("configs/research_status.json"),
        "bakeoff": {"source": "results/real_desktop_ml/decision-tree-demo/summary.json",
                    "summary": read_json("results/real_desktop_ml/decision-tree-demo/summary.json")}}


def _run(jobs, algorithm):
    if algorithm == "Tuned MLFQ":
        parameters = read_json("configs/research_status.json")["recommended_static"]["parameters"]
        return run_simulation(algorithm, mlfq, jobs, **parameters)
    registry = {**ALGORITHMS, **DEPLOYABLE_ALGORITHMS}
    if algorithm not in registry:
        raise ValueError("Choose an available scheduling algorithm.")
    scheduler, kwargs = registry[algorithm]
    return run_simulation(algorithm, scheduler, jobs, **kwargs)


def _frames(jobs, result):
    """Reconstruct playback membership and cumulative waiting without rescheduling."""
    by_pid = {p.pid: p for p in jobs}
    slices = {p.pid: [(start, end) for pid, start, end in result.timeline if pid == p.pid] for p in jobs}
    io_intervals = {}
    for job in jobs:
        intervals, threshold = [], 0
        for cpu, duration in zip(job.cpu_bursts, job.io_bursts):
            threshold += cpu
            used = 0
            for start, end in slices[job.pid]:
                if used < threshold <= used + end - start:
                    io_start = start + threshold - used
                    intervals.append((io_start, io_start + duration))
                    break
                used += end - start
        io_intervals[job.pid] = intervals
    frames = []
    for tick in range(result.makespan + 1):
        running = next((pid for pid, start, end in result.timeline if start <= tick < end), None)
        rows, ready, blocked = [], [], []
        for metric in sorted(result.process_metrics, key=lambda m: m.pid):
            job = by_pid[metric.pid]
            effective = min(tick, metric.completion_time)
            service = sum(max(0, min(effective, end) - start) for start, end in slices[job.pid] if start < effective)
            io_time = sum(max(0, min(effective, end) - start) for start, end in io_intervals[job.pid] if start < effective)
            if tick < job.arrival_time:
                state = "Not arrived"
            elif tick >= metric.completion_time:
                state = "Completed"
            elif any(start <= tick < end for start, end in io_intervals[job.pid]):
                state = "Blocked"
                blocked.append(job.pid)
            elif running == job.pid:
                state = "Running"
            else:
                state = "Ready"
                ready.append(job.pid)
            rows.append({"pid": job.pid, "arrival_time": job.arrival_time, "burst_time": job.burst_time,
                "priority": job.priority, "state": state,
                "waiting_time": max(0, effective - job.arrival_time - service - io_time),
                "response_time": metric.response_time if tick >= metric.start_time else None,
                "turnaround_time": metric.turnaround_time if tick >= metric.completion_time else None})
        frames.append({"tick": tick, "running": running, "ready": ready, "blocked": blocked, "processes": rows,
                       "completed": sum(p["state"] == "Completed" for p in rows)})
    return frames


@lru_cache(maxsize=24)
def simulation(workload="short_jobs", algorithm="Round Robin"):
    jobs = processes(workload)
    result = _run(jobs, algorithm)
    data = asdict(result)
    data.pop("process_metrics")
    return {"workload": workload, "algorithm": algorithm, "metrics": data,
        "timeline": result.timeline, "processes": [asdict(m) for m in result.process_metrics],
        "frames": _frames(jobs, result), "features": extract_features(jobs),
        "queue_note": "Ready membership reconstructed from CPU service and I/O intervals; policy queue order is not exposed."}


@lru_cache(maxsize=3)
def comparison(workload="short_jobs"):
    jobs = processes(workload)
    references = compare_algorithms(jobs)
    results = {**references, "MLFQ": _run(jobs, "MLFQ"), "Tuned MLFQ": _run(jobs, "Tuned MLFQ")}
    rows = []
    for name, result in results.items():
        response = sorted(m.response_time for m in result.process_metrics)
        position = (len(response)-1)*.95
        low = int(position)
        p95 = response[low] + (response[min(low+1,len(response)-1)]-response[low])*(position-low)
        rows.append({"algorithm": name, "score": score_result_against_reference(result, references),
            "waiting": result.avg_waiting_time, "turnaround": result.avg_turnaround_time,
            "response": result.avg_response_time, "p95_response": p95, "utilization": result.cpu_utilization,
            "throughput": result.throughput, "context_switches": result.context_switches,
            "starvation": aggregate_fairness(result.process_metrics)["starvation_count"],
            "oracle_only": name in ("SJF", "SRTF")})
    return {"workload": workload, "scope": "One tiny hand-defined demo; not a research benchmark or model-selection dataset.",
            "score_reference": "Fixed bounds from the six traditional policies on this same workload; lower is better, values may exceed [0,1].",
            "results": sorted(rows, key=lambda row: row["score"])}
