"""Read-only reports for the same cohorts and calculations used by the dashboard."""
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
AZURE = "results/dynamic_azure_generalization/"
RETRAINED = "results/dynamic_v5_azure_retrained_20261020/"
MODEL = "artifacts/dynamic_v5_20261019/policy_cost/model.joblib"
AZURE_FIELDS = (
    "weighted_score", "avg_waiting_ms", "avg_response_ms", "p95_response_ms",
    "avg_turnaround_ms", "starvation", "context_switches", "throughput_jobs_per_ms",
    "utilization_fraction", "accepted_switches", "decision_p99_ms",
)


def read(path):
    return json.loads((ROOT / path).read_text())


def aggregate_rows(rows, policies, fields):
    """Average workload metrics over identical complete inputs; retain failures."""
    grouped = defaultdict(dict)
    for row in rows:
        wid, policy = row["workload_id"], row["policy"]
        if policy in grouped[wid]:
            raise ValueError(f"Duplicate workload/policy row: {wid}, {policy}")
        grouped[wid][policy] = row
    common = sorted(wid for wid, group in grouped.items()
                    if all(p in group and group[p]["status"] == "COMPLETE" for p in policies))
    means, counts = {}, {}
    for policy in policies:
        means[policy], counts[policy] = {}, {}
        for field in fields:
            values = [float(grouped[wid][policy][field]) for wid in common
                      if grouped[wid][policy].get(field) not in (None, "")]
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"Nonfinite metric: {policy}, {field}")
            means[policy][field] = mean(values) if values else None
            counts[policy][field] = len(values)
    return {"selected_workloads": len(grouped), "completed_workloads": len(common),
            "common_workload_ids": common, "incomplete_workload_ids": sorted(set(grouped) - set(common)),
            "failures": [r for r in rows if r["status"] != "COMPLETE"],
            "means": means, "metric_sample_counts": counts}


def compare(value, baseline, higher=False):
    """Match dashboard/web/src/comparisons.js, including ties and zero references."""
    if value is None or baseline is None or not all(math.isfinite(x) for x in (value, baseline)):
        return {"winner": None, "percent": None, "status": "unmeasured"}
    delta = (1 if higher else -1) * (value - baseline)
    if abs(delta) <= max(1, abs(value), abs(baseline)) * 1e-12:
        return {"winner": None, "percent": 0, "status": "tie"}
    winner = "v5" if delta > 0 else "baseline"
    reference = abs(baseline) if winner == "v5" else abs(value)
    return {"winner": winner, "percent": abs(value - baseline) / reference * 100 if reference else None,
            "status": "compared"}


def prediction_report(retrained=False):
    """Fresh inference on existing development labels; no fit or holdout access."""
    import numpy as np
    from autoscheduler.azure_regression_comparison import metrics
    from autoscheduler.azure_v5_retrain import validate_splits
    from autoscheduler.dynamic import DYNAMIC_FEATURE_NAMES, DynamicRouterConfig
    from autoscheduler.model import load_model

    protocol = read(RETRAINED + "protocol.json")
    data = "artifacts/dynamic_v5_azure_retrained/decision_costs.json"
    rows = read(data)
    reserved = read("results/azure_adapted_20261020/protocol.json")["reserved_holdout_groups"]
    validate_splits(rows, set(reserved))
    saved_original = read("results/original_v5_azure_prediction_20261020/metrics.json")
    model_path = "artifacts/dynamic_v5_azure_retrained/model.joblib" if retrained else MODEL
    expected = read(RETRAINED + "frozen_model.json")["sha256"] if retrained else saved_original["model_sha256"]
    if hashlib.sha256((ROOT / model_path).read_bytes()).hexdigest() != expected:
        raise ValueError(f"Model hash differs from verified artifact: {model_path}")
    if hashlib.sha256((ROOT / data).read_bytes()).hexdigest() != saved_original["data_sha256"]:
        raise ValueError("Labeled data differs from verified development data")
    if tuple(protocol["features"]) != DYNAMIC_FEATURE_NAMES:
        raise ValueError("Feature order differs from current v5 contract")
    model = load_model(ROOT / model_path, DYNAMIC_FEATURE_NAMES,
                       expected_dynamic_config=DynamicRouterConfig(**protocol["config"]))
    if tuple(protocol["actions"]) != model.policies:
        raise ValueError("Action-cost output order differs from labeled data")
    training = np.array([r["costs"] for r in rows if r["split"] == "train"])
    splits = {}
    for split in (("train", "validation", "test") if retrained else ("test",)):
        subset = [r for r in rows if r["split"] == split]
        x = np.array([[r["features"][name] for name in DYNAMIC_FEATURE_NAMES] for r in subset])
        actual = np.array([r["costs"] for r in subset])
        if not all(np.isfinite(a).all() for a in (x, actual, training)):
            raise ValueError("Nonfinite feature or target")
        predicted = model.regressor.predict(x)
        selected = np.argmin(predicted, axis=1)
        strict = np.mean(selected == np.argmin(actual, axis=1))
        tied = np.mean(actual[np.arange(len(subset)), selected] <= np.min(actual, axis=1) + 1e-12)
        splits[split] = {"decision_rows": len(subset), "groups": len({r["source_group"] for r in subset}),
                         **metrics(actual, predicted), "strict_action_agreement": float(strict),
                         "tie_aware_action_agreement": float(tied),
                         "training_mean_dummy": metrics(actual, np.tile(training.mean(axis=0), (len(subset), 1)))}
    return {"calculation": "fresh fitted-model inference; no training", "model": model_path,
            "data": data, "scope": "previously examined development partitions, not independent validation",
            "target_units": "dimensionless score deltas versus MLFQ continuation",
            "dummy_reference": {"training_states": len(training),
                                "training_groups": len({r["source_group"] for r in rows if r["split"] == "train"})},
            "actions": list(model.policies), "splits": splits}


def azure_report(retrained=False):
    """Recalculate displayed schedule means from per-workload saved outcomes."""
    if retrained:
        source = RETRAINED + "workload_results.json"
        rows = read(source)
        policies = ("Original v5", "Azure-retrained v5", "Tuned MLFQ")
        fields = AZURE_FIELDS[:6]
        saved = read(RETRAINED + "results.json")
    else:
        source = AZURE + "baseline_rows.json"
        rows = read(source)["rows"]
        policies = ("FCFS", "Round Robin", "Priority", "Priority RR", "MLFQ", "Tuned MLFQ", "Dynamic v5")
        fields = AZURE_FIELDS
        saved = read(AZURE + "summary.json")
        # Match the report's correction: an empty instrumentation list is not zero latency.
        for row in rows:
            if row["policy"] in {"FCFS", "Round Robin", "Priority", "Priority RR"}:
                row["decision_p99_ms"] = None
    scheduling = aggregate_rows(rows, policies, fields)
    common = set(scheduling["common_workload_ids"])
    totals = {p: sum(r.get("accepted_switches", 0) for r in rows
                     if r["policy"] == p and r["workload_id"] in common) for p in policies}
    report = {"calculation": "means and comparisons recalculated from saved per-workload outcomes",
              "source": source, "units": "1 simulator tick = 1 ms; wall-clock durations proxy CPU demand",
              "scope": "six examined development workloads" if retrained else "17 selected; common-complete subset only",
              "scheduling": scheduling, "accepted_switch_totals": totals,
              "historical_gates_not_rerun": saved["gates"],
              "notes": "No scheduling replay, training, locked-holdout access or saved-result overwrite."}
    candidate = "Azure-retrained v5" if retrained else "Dynamic v5"
    report["candidate"] = candidate
    report["overhead"] = {}
    for policy in policies:
        latencies = [r["decision_p99_ms"] * 1000 for r in rows
                     if r["policy"] == policy and r["workload_id"] in common
                     and r.get("decision_p99_ms") is not None]
        report["overhead"][policy] = {
            "mean_workload_p99_us": mean(latencies) if latencies else None,
            "max_workload_p99_us": max(latencies) if latencies else None,
            "controller_total_ms": None,
        }
    report["comparisons_vs_tuned_mlfq"] = {
        key: compare(value, scheduling["means"]["Tuned MLFQ"][key],
                     higher=key in {"throughput_jobs_per_ms", "utilization_fraction"})
        for key, value in scheduling["means"][candidate].items() if key not in {"accepted_switches", "decision_p99_ms"}}
    if not retrained:
        decisions = [r for r in read(AZURE + "baseline_decisions.json")["rows"]
                     if r["complete"] and r["workload_id"] in common]
        report["decision_totals"] = {"reviews": sum(r["decisions"] for r in decisions),
                                      "accepted": sum(r["accepted_switches"] for r in decisions)}
        report["decision_totals"]["nonaccepted"] = report["decision_totals"]["reviews"] - report["decision_totals"]["accepted"]
        report["historical_paired_confidence_intervals"] = saved["paired_comparisons_dynamic_minus_static"]["Tuned MLFQ"]
        report["historical_earlier_pilot_separate_cohort"] = read("results/azure_external_pilot/summary.json")
    else:
        report["historical_paired_confidence_intervals"] = saved["paired_differences_95ci"]
        report["historical_max_routing_p99_ms"] = saved["routing_p99_max_ms"]
    return report


def synthetic_report(version=5):
    source = f"results/dynamic_v{version}_20261019/audit/workloads.csv"
    with (ROOT / source).open(newline="") as stream:
        rows = [{**r, "workload_id": r["seed"], "status": "COMPLETE"} for r in csv.DictReader(stream)]
    fields = ("score", "p95_response", "worst_response", "starvation", "switches",
              "decision_p99_ms", "guard_blocks", "safety_returns", "dwell_blocks")
    policies = tuple(dict.fromkeys(r["policy"] for r in rows))
    calculated = aggregate_rows(rows, policies, fields)
    return {"calculation": "arithmetic means recomputed from saved audit CSV; no new synthetic evaluation",
            "source": source, "units": "synthetic ticks; decision_p99_ms is host wall time",
            "version": version,
            "workloads": calculated["completed_workloads"], "means": calculated["means"],
            "historical_audit_details": read(f"results/dynamic_v{version}_20261019/audit/summary.json"),
            "historical_training_reports": {kind: read(f"results/dynamic_v{version}_20261019/{kind}_training.json")
                                            for kind in ("classifier", "policy_cost")},
            "historical_offline_classifier_metadata": read("artifacts/demo_tree.json"),
            "historical_fixed_baseline_sensitivity": read("results/dynamic_v6_20261019/sensitivity.json") if version == 6 else None,
            "notes": "Recorded pooled P99 and confidence intervals are retained, not inferred from mean workload P99s."}


def demo_report(workload=None, algorithm=None):
    from dashboard.adapter import WORKLOADS, catalog, comparison, simulation

    workloads = {}
    for wid in ([workload] if workload else WORKLOADS):
        policies = {}
        for name in ([algorithm] if algorithm else catalog()["algorithms"]):
            result = simulation(wid, name)
            policies[name] = {key: result[key] for key in (
                "metrics", "processes", "features", "policy_transitions", "routing_decisions",
                "dynamic_model", "response_comparison", "reproducibility")}
            if result["dynamic_model"]:
                policies[name]["overhead"] = result["overhead"]
        workloads[wid] = {"policies": policies, "comparison": comparison(wid)}
    return {"calculation": "computed now by the same backend functions as /api/simulation and /api/comparison",
            "scope": "tiny hand-defined dashboard demonstrations, not a benchmark or training data",
            "units": "simulator ticks; controller transition_ms is measured host wall time",
            "workloads": workloads}


def latency_totals(decisions, makespan, cpu_ticks, wall_ms, tick_ms):
    from autoscheduler.dynamic import _percentile

    times = [d.transition_ms for d in decisions]
    total = sum(times)
    return {"reviews": len(times), "accepted_switches": sum(d.accepted for d in decisions),
            "controller_total_ms": total, "decision_mean_us": mean(times) * 1000 if times else None,
            "decision_p50_us": _percentile(times, .50) * 1000 if times else None,
            "decision_p95_us": _percentile(times, .95) * 1000 if times else None,
            "decision_p99_us": _percentile(times, .99) * 1000 if times else None,
            "decision_max_us": max(times) * 1000 if times else None,
            "makespan_ticks": makespan, "cpu_proxy_ticks": cpu_ticks, "ms_per_tick": tick_ms,
            "controller_vs_makespan_percent": 100 * total / (makespan * tick_ms) if makespan and tick_ms else None,
            "controller_vs_cpu_proxy_percent": 100 * total / (cpu_ticks * tick_ms) if cpu_ticks and tick_ms else None,
            "python_simulation_wall_ms": wall_ms,
            "controller_share_python_wall_percent": 100 * total / wall_ms if wall_ms else None}


def latency_report(suite="demo", *, repeats=None, warmups=5, limit=None, timeout_seconds=20,
                   model_name="original", version=5, azure_cohort=None):
    """Measure a frozen controller without changing scheduling logic or artifacts."""
    import signal
    from time import perf_counter
    from dashboard.adapter import WORKLOADS, _original_v5, processes
    from autoscheduler.dynamic import run_dynamic
    from simulator.process import Process

    repeats = (30 if suite == "demo" else 1) if repeats is None else repeats
    if repeats < 1 or warmups < 0 or timeout_seconds < 1 or (limit is not None and limit < 1):
        raise ValueError("repeats, limit and timeout must be positive; warmups must be nonnegative")
    if suite == "demo":
        items = [(name, processes(name)) for name in WORKLOADS]
    elif suite == "azure":
        cohort = azure_cohort or model_name
        if cohort not in {"original", "retrained"}:
            raise ValueError("Azure cohort must be original or retrained")
        common = set(azure_report(cohort == "retrained")["scheduling"]["common_workload_ids"])
        items = [(w["workload_id"], [Process(**p) for p in w["processes"]])
                 for w in read("AzureWorkloads/cleaned/evaluation_workloads.json")["workloads"]
                 if w["workload_id"] in common]
        items.sort(key=lambda item: item[0])
        if {wid for wid, _ in items} != common:
            raise ValueError("Azure timing inputs do not cover the complete selected cohort")
    elif suite == "synthetic":
        from autoscheduler.development_workloads import DEV_FAMILIES, generate_development_workload_v4
        protocol = read(f"results/dynamic_v{version}_20261019/protocol.json")
        items = []
        for i in range(protocol["traces"]["audit"]):
            seed = protocol["seeds"]["audit"] * 1_000_000 + i
            workload = generate_development_workload_v4(seed, DEV_FAMILIES[i % len(DEV_FAMILIES)])
            items.append((str(seed), workload.processes))
    else:
        raise ValueError("suite must be demo, synthetic or azure")
    available = len(items)
    items = items[:limit] if limit is not None else items
    model_path = MODEL
    if model_name == "original" and version == 5:
        model, config = _original_v5()
    else:
        from autoscheduler.dynamic import DYNAMIC_FEATURE_NAMES, DynamicRouterConfig
        from autoscheduler.model import load_model, load_model_metadata
        if model_name == "retrained":
            model_path = "artifacts/dynamic_v5_azure_retrained/model.joblib"
            expected = read(RETRAINED + "frozen_model.json")["sha256"]
        elif model_name == "original" and version == 6:
            model_path = "artifacts/dynamic_v6_20261019/policy_cost/model.joblib"
            expected = read("results/dynamic_v6_20261019/research_summary.json")["model_sha256"]["policy_cost"]
        else:
            raise ValueError("Unknown timing model/version")
        if hashlib.sha256((ROOT / model_path).read_bytes()).hexdigest() != expected:
            raise ValueError("Timing model differs from its frozen artifact")
        config = DynamicRouterConfig(**load_model_metadata(ROOT / model_path)["dynamic_config"])
        model = load_model(ROOT / model_path, DYNAMIC_FEATURE_NAMES, expected_dynamic_config=config)
    # Warm imports/model code on tiny jobs, never on the reserved Azure holdout.
    for _ in range(warmups):
        run_dynamic(processes("short_jobs"), model, config)
    records, all_decisions, failures = [], [], []
    total_span = total_cpu = total_wall = 0

    def expired(*_):
        raise TimeoutError(f"{timeout_seconds}-second per-workload limit")

    if signal.getitimer(signal.ITIMER_REAL)[0]:
        raise ValueError("Cannot replace an active timeout")
    previous = signal.signal(signal.SIGALRM, expired)
    try:
        for wid, jobs in items:
            decisions, span, cpu, wall = [], 0, 0, 0
            completed = 0
            schedule_metrics = None
            for run in range(repeats):
                started = perf_counter()
                signal.alarm(timeout_seconds)
                try:
                    result = run_dynamic(jobs, model, config)
                except TimeoutError as error:
                    failures.append({"workload_id": wid, "run": run + 1, "status": "TIMEOUT", "reason": str(error)})
                    break
                finally:
                    signal.alarm(0)
                wall += (perf_counter() - started) * 1000
                decisions.extend(result.decisions)
                span += result.simulation.makespan
                cpu += sum(p.burst_time for p in jobs)
                completed += 1
                schedule_metrics = {"avg_waiting_ms": result.simulation.avg_waiting_time,
                                    "avg_response_ms": result.simulation.avg_response_time,
                                    "avg_turnaround_ms": result.simulation.avg_turnaround_time} if suite == "azure" else None
            tick_ms = 1 if suite == "azure" else None
            records.append({"workload_id": wid, "processes": len(jobs), "requested_runs": repeats,
                            "completed_runs": completed, "status": "COMPLETE" if completed == repeats else "TIMEOUT",
                            "schedule_metrics": schedule_metrics,
                            "timing": latency_totals(decisions, span, cpu, wall, tick_ms)})
            all_decisions.extend(decisions)
            total_span += span
            total_cpu += cpu
            total_wall += wall
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
    p99s = [r["timing"]["decision_p99_us"] for r in records if r["timing"]["reviews"]]
    return {"calculation": "fresh timing-only replay of frozen fitted controller; no training",
            "azure_cohort": (azure_cohort or model_name) if suite == "azure" else None,
            "suite": suite, "available_workloads": available, "selected_workloads": len(items),
            "completed_runs": sum(r["completed_runs"] for r in records), "warmups": warmups,
            "model": model_path, "model_sha256": hashlib.sha256((ROOT / model_path).read_bytes()).hexdigest(),
            "timing_scope": "features, predictions, margin, safeguards and accepted-switch queue update; excludes model load, dispatch, API and playback",
            "aggregation": "pooled decision samples; elapsed controller time is summed, never estimated from P99",
            "units_note": "Only Azure has 1 tick = 1 ms. Ratios are illustrative time budgets; overhead is not charged to simulated time or measured as kernel slowdown.",
            "coverage_note": "Azure replays only previously complete development workloads for the named model/cohort (12 original or 6 retrained), never the final holdout. Timeouts are retained; partial timeout-run measurements are excluded.",
            "max_workload_p99_us": max(p99s) if p99s else None,
            "complete_coverage_p99_lt_10ms": not failures and bool(p99s) and max(p99s) < 10000,
            "workloads": records, "failures": failures,
            "pooled": latency_totals(all_decisions, total_span, total_cpu, total_wall, 1 if suite == "azure" else None)}


def bakeoff_report():
    source = "results/real_desktop_ml/decision-tree-demo/summary.json"
    return {"calculation": "saved offline-replay model comparison; no fitting or new evaluation",
            "source": source, "results": read(source),
            "note": "These regression families and their cohort are separate from original v5; agreement is not classifier training accuracy."}


def run_cli(kind):
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=f"Read-only {kind.replace('_', ' ')} metrics. No model training or saved-result overwrite.")
    parser.add_argument("--json", action="store_true", help="emit full structured JSON instead of presentation tables")
    if kind in {"synthetic", "azure", "azure_retrained"}:
        parser.add_argument("--measure-overhead", action="store_true", help="also measure cumulative controller overhead on this report's cohort")
    if kind == "demo":
        parser.add_argument("--workload", help="one dashboard workload ID; default: all four")
        parser.add_argument("--algorithm", help="one dashboard algorithm name; default: all")
    elif kind == "synthetic":
        parser.add_argument("--version", choices=(5, 6), type=int, default=5)
    elif kind == "latency":
        parser.add_argument("--suite", choices=("demo", "synthetic", "azure"), default="demo")
        parser.add_argument("--repeats", type=int, help="default: 30 per demo workload, 1 otherwise")
        parser.add_argument("--warmups", type=int, default=5, help="tiny-job warmups before measurement")
        parser.add_argument("--limit", type=int, help="maximum workloads to replay; default: whole selected suite")
        parser.add_argument("--timeout-seconds", type=int, default=20, help="per-run wall-clock cap")
        parser.add_argument("--model", choices=("original", "retrained"), default="original")
        parser.add_argument("--version", choices=(5, 6), type=int, default=5)
    args = parser.parse_args()
    try:
        if kind == "demo":
            report = demo_report(args.workload, args.algorithm)
        elif kind == "synthetic":
            report = synthetic_report(args.version)
        elif kind in {"azure", "azure_retrained"}:
            report = azure_report(kind == "azure_retrained")
            report["regression"] = prediction_report(kind == "azure_retrained")
        elif kind == "latency":
            report = latency_report(args.suite, repeats=args.repeats, warmups=args.warmups,
                                    limit=args.limit, timeout_seconds=args.timeout_seconds,
                                    model_name=args.model, version=args.version)
        else:
            report = bakeoff_report()
        if getattr(args, "measure_overhead", False):
            print("Measuring controller overhead on the matching cohort...", file=sys.stderr)
            report["fresh_overhead"] = latency_report(
                "synthetic" if kind == "synthetic" else "azure", repeats=1,
                model_name="retrained" if kind == "azure_retrained" else "original",
                version=getattr(args, "version", 5))
        if args.json:
            print(json.dumps(report, indent=2, allow_nan=False))
        else:
            from autoscheduler.metric_tables import print_report
            print_report(kind, report, details=bool(getattr(args, "algorithm", None)))
        if report.get("failures") or report.get("fresh_overhead", {}).get("failures"):
            return 1
        return 0
    except (OSError, ImportError, ValueError, KeyError) as error:
        print(f"Metrics unavailable: {error}", file=sys.stderr)
        return 1
