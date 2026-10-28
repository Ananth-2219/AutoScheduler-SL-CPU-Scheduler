"""Explicit timing-only snapshots; loading the dashboard never replays research."""
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "dashboard/generated/controller_overhead.json"


@lru_cache(maxsize=64)
def _hash_file(name, size, modified):
    with (ROOT / name).open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def fingerprints():
    """Bind measurements to fitted models, replay inputs, code and saved cohorts."""
    names = [
        "AzureWorkloads/cleaned/evaluation_workloads.json",
        "results/dynamic_azure_generalization/baseline_rows.json",
        "results/dynamic_v5_azure_retrained_20261020/workload_results.json",
        "artifacts/dynamic_v5_azure_retrained/model.joblib",
        "configs/research_status.json", "autoscheduler/review_metrics.py",
        "autoscheduler/development_workloads.py", "autoscheduler/model.py",
        "autoscheduler/dynamic.py", "simulator/process.py", "simulator/simulator.py",
        "simulator/engine.py", "dashboard/overhead.py", "dashboard/adapter.py",
    ]
    for version in (5, 6):
        names.extend([f"artifacts/dynamic_v{version}_20261019/policy_cost/model.joblib",
                      f"results/dynamic_v{version}_20261019/protocol.json",
                      f"results/dynamic_v{version}_20261019/audit/workloads.csv"])
    result = {}
    for name in names:
        stat = (ROOT / name).stat()
        result[name] = _hash_file(name, stat.st_size, stat.st_mtime_ns)
    return result


def load_snapshot(path=SNAPSHOT):
    empty = {"status": "unavailable", "cohorts": {},
             "reason": "Controller totals have not been measured locally. Run python3 scripts/measure_dashboard_overhead.py."}
    try:
        snapshot = json.loads(Path(path).read_text())
        if snapshot.get("schema_version") != 1 or snapshot.get("fingerprints") != fingerprints():
            return {**empty, "status": "stale", "reason": "Timing inputs or code changed. Refresh the overhead snapshot."}
        return snapshot
    except (OSError, ValueError, AttributeError):
        return empty


def verify_azure_replay(report, saved_rows, policy):
    """Do not pair new timing with different historical scheduling outcomes."""
    expected = {r["workload_id"]: r for r in saved_rows if r["policy"] == policy and r["status"] == "COMPLETE"}
    for row in report["workloads"]:
        if row["status"] != "COMPLETE":
            continue
        saved = expected[row["workload_id"]]
        for name, value in row["schedule_metrics"].items():
            if not math.isclose(value, saved[name], rel_tol=1e-10, abs_tol=1e-9):
                raise ValueError(f"Timing replay changed scheduling outcome: {policy}, {row['workload_id']}, {name}")


def measure_snapshot(progress=print):
    from autoscheduler.review_metrics import latency_report, read, AZURE, RETRAINED

    before = fingerprints()
    original = read(AZURE + "baseline_rows.json")["rows"]
    retrained = read(RETRAINED + "workload_results.json")
    specs = [
        ("azure_original", "Panel A · 12 completed Azure workloads", "Dynamic ML (v5)",
         dict(suite="azure", model_name="original"), original, "Dynamic v5"),
        ("azure_retrained", "Panel B · six Azure development workloads", "Original v5",
         dict(suite="azure", model_name="original", azure_cohort="retrained"), retrained, "Original v5"),
        ("azure_retrained", "Panel B · six Azure development workloads", "Azure-retrained v5",
         dict(suite="azure", model_name="retrained"), retrained, "Azure-retrained v5"),
        ("synthetic_v5", "Original v5 · 240 synthetic audit workloads", "Dynamic ML (v5)",
         dict(suite="synthetic", version=5), None, None),
        ("synthetic_v6", "V6 · 240 synthetic audit workloads", "Dynamic ML (v6)",
         dict(suite="synthetic", version=6), None, None),
    ]
    cohorts = {}
    for key, label, policy, kwargs, saved, saved_policy in specs:
        progress(f"Measuring {label}: {policy} ...", flush=True)
        report = latency_report(**kwargs)
        if saved is not None:
            verify_azure_replay(report, saved, saved_policy)
        cohort = cohorts.setdefault(key, {"label": label, "entries": []})
        cohort["entries"].append({"policy": policy, **report})
        totals = report["pooled"]
        progress(f"  {report['completed_runs']}/{report['selected_workloads']} completed; "
                 f"controller total {totals['controller_total_ms']:.3f} ms", flush=True)
    if before != fingerprints():
        raise ValueError("Timing inputs changed during measurement; snapshot was not saved")
    return {"schema_version": 1, "status": "measured", "measured_at": datetime.now(timezone.utc).isoformat(),
            "host": {"platform": platform.platform(), "python": platform.python_version()},
            "fingerprints": before, "cohorts": cohorts}


def main():
    snapshot = measure_snapshot()
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    temporary = SNAPSHOT.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n")
    temporary.replace(SNAPSHOT)
    print(f"Saved {SNAPSHOT}")
    return int(any(entry["failures"] for c in snapshot["cohorts"].values() for entry in c["entries"]))
