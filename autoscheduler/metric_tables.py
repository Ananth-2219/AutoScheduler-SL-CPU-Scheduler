"""Plain terminal tables for review reports; all values come from report data."""


def number(value, digits=3):
    return "--" if value is None else f"{value:,.{digits}f}"


def table(headers, rows):
    rows = [[str(x) for x in row] for row in rows]
    widths = [max([len(str(h)), *(len(row[i]) for row in rows)]) for i, h in enumerate(headers)]
    def line(row):
        return " | ".join(str(cell).ljust(widths[i]) if i == 0 else str(cell).rjust(widths[i])
                          for i, cell in enumerate(row))
    print(line(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(line(row))
    print()


def heading(text):
    print(f"\n{text}\n{'=' * len(text)}")


def gates(values):
    table(("Safety gate (saved evaluation)", "Result"), [
        (key.replace("conditional_primary_", "").replace("_", " "),
         "PASS" if value is True else "FAIL" if value is False else str(value))
        for key, value in values.items()])


def regression(report):
    heading("REGRESSION QUALITY / FRESH INFERENCE")
    table(("Split", "States", "Groups", "MAE", "RMSE", "R2", "Action match %", "Tie-aware %"), [
        (split, row["decision_rows"], row["groups"], number(row["mae"], 6),
         number(row["rmse"], 6), number(row["r_squared"]),
         number(row["strict_action_agreement"] * 100, 2), number(row["tie_aware_action_agreement"] * 100, 2))
        for split, row in report["splits"].items()])
    dummy = report["splits"]["test"]["training_mean_dummy"]
    print(f"Training-mean dummy, same test: MAE {number(dummy['mae'], 6)} | "
          f"RMSE {number(dummy['rmse'], 6)} | R2 {number(dummy['r_squared'])}")
    print("R2 is regression fit; action agreement is not scheduling improvement.")
    print(f"Scope: {report['scope']}\nModel: {report['model']}")


def azure(report):
    candidate = report["candidate"]
    heading(f"{candidate.upper()} / AZURE FUNCTIONS 2019")
    schedule = report["scheduling"]
    print(f"Completed / selected workloads: {schedule['completed_workloads']} / {schedule['selected_workloads']}"
          f" | Retained policy timeouts: {len(schedule['failures'])}")
    print("Recalculated from saved workload outcomes. Reconstructed real-source simulation; 1 tick = 1 ms.")
    current, baseline = schedule["means"][candidate], schedule["means"]["Tuned MLFQ"]
    labels = [("avg_waiting_ms", "Average waiting (ms)", 3),
              ("weighted_score", "Weighted score", 6), ("avg_response_ms", "Average first response (ms)", 3),
              ("p95_response_ms", "Mean workload P95 response (ms)", 4),
              ("avg_turnaround_ms", "Average turnaround (ms)", 3),
              ("starvation", "Starvation flags / workload", 3),
              ("context_switches", "PID switches / workload", 3),
              ("throughput_jobs_per_ms", "Throughput (jobs/ms)", 8),
              ("utilization_fraction", "CPU utilization (%)", 3)]
    rows = []
    for key, label, digits in labels:
        if key not in current:
            continue
        a, b = current[key], baseline[key]
        if key == "utilization_fraction":
            a, b = a * 100 if a is not None else None, b * 100 if b is not None else None
        comparison = report["comparisons_vs_tuned_mlfq"][key]
        winner = "Tie" if comparison["status"] == "tie" else (
            candidate if comparison["winner"] == "v5" else "Tuned MLFQ" if comparison["winner"] else "Not measured")
        change = "" if comparison["percent"] is None or comparison["status"] == "tie" else f" ({comparison['percent']:.2f}%)"
        rows.append((label, number(a, digits), number(b, digits), winner + change))
    heading("SCHEDULING PERFORMANCE")
    table(("Metric", candidate, "Tuned MLFQ", "Better result"), rows)
    print("P95 is averaged over workloads. Percentages follow the dashboard's winner/reference formula.")
    if "Original v5" in schedule["means"]:
        table(("Same six-workload cohort", "Score", "Waiting ms", "P95 ms", "Accepted switches"), [
            (name, number(row["weighted_score"], 6), number(row["avg_waiting_ms"]),
             number(row["p95_response_ms"]), report["accepted_switch_totals"][name])
            for name, row in schedule["means"].items()])
    if "decision_totals" in report:
        counts = report["decision_totals"]
        print(f"Controller reviews: {counts['reviews']:,} | Accepted transitions: {counts['accepted']:,}"
              f" | Nonaccepted reviews: {counts['nonaccepted']:,}")
    heading("CONTROLLER OVERHEAD / SAVED MATCHING COHORT")
    table(("Policy", "Mean workload P99 (us)", "Worst workload P99 (us)"), [
        (name, number(row["mean_workload_p99_us"]), number(row["max_workload_p99_us"]))
        for name, row in report["overhead"].items()])
    print("Cumulative overhead and overhead/completion ratio: not recorded in these historical rows.")
    print("Use --measure-overhead to calculate them now. P99 is not an average or a cumulative total.")
    print("Static MLFQ timings cover ready selection; dynamic timings include features, model and guards.")
    if "regression" in report:
        regression(report["regression"])
    heading("ACCEPTANCE STATUS")
    gates(report["historical_gates_not_rerun"])
    print("Recommendation: retain tuned MLFQ; no ML model promoted.")
    if schedule["failures"]:
        heading("RETAINED TIMEOUTS")
        table(("Workload", "Policy", "Status"), [(r["workload_id"], r["policy"], r["status"])
                                                for r in schedule["failures"]])
    print(f"Source: {report['source']}")


def synthetic(report):
    heading(f"SYNTHETIC DEVELOPMENT / V{report['version']}")
    names = {"policy_cost": f"Dynamic v{report['version']} (cost tree)",
             "classifier": f"Dynamic v{report['version']} (classifier)",
             "MLFQ control": "MLFQ control (no model)"}
    print(f"Workloads: {report['workloads']} | Recalculated from saved audit outcomes | Time unit: ticks")
    heading("SCHEDULING PERFORMANCE")
    table(("Policy / model", "Weighted score", "Mean P95 (ticks)", "Starvation", "Switches/run"), [
        (names.get(name, name), number(row["score"], 6), number(row["p95_response"]), number(row["starvation"]), number(row["switches"]))
        for name, row in report["means"].items()])
    heading("CONTROLLER OVERHEAD / SAVED SYNTHETIC AUDIT")
    table(("Controller", "Pooled P99 (us)", "Worst workload P99 (us)"), [
        (names.get(name, name), number(row.get("pooled_routing_p99_ms") * 1000 if row.get("pooled_routing_p99_ms") is not None else None),
         number(row.get("max_workload_decision_p99_ms") * 1000 if row.get("max_workload_decision_p99_ms") is not None else None))
        for name, row in report["historical_audit_details"].items()
        if row.get("pooled_routing_p99_ms") is not None or row.get("max_workload_decision_p99_ms") is not None])
    print("Cumulative overhead: not recorded. Use --measure-overhead for fresh cumulative measurements.")
    print("Overhead/completion percentage: N/A; synthetic ticks have no calibrated ms mapping.")
    heading("MODEL TRAINING / SAVED INTERNAL TEST")
    table(("Model family", "Rows", "Validation match %", "Test match %", "Tie-aware test %"), [
        (names.get(name, name), row["rows"], number(row["validation_accuracy"] * 100, 2),
         number(row["test_accuracy"] * 100, 2),
         number(row["test_tie_aware_accuracy"] * 100 if row.get("test_tie_aware_accuracy") is not None else None, 2))
        for name, row in report["historical_training_reports"].items()])
    print("Action agreement is not scheduling performance. These are synthetic development results.")
    old = report["historical_offline_classifier_metadata"]
    print(f"Separate historical offline classifier: {old['rows']:,} workload rows | "
          f"Validation {old['validation_accuracy'] * 100:.2f}% | Test {old['test_accuracy'] * 100:.2f}%")
    print("Offline classifier runtime overhead: not recorded in this metadata.")
    print(f"Source: {report['source']}")


def demo(report, details):
    heading("DASHBOARD DEMONSTRATIONS / COMPUTED NOW")
    print("Same backend as the dashboard. Synthetic ticks; not measured OS scheduling.")
    for wid, workload in report["workloads"].items():
        heading(wid.replace("_", " ").upper())
        table(("Policy", "Score", "Waiting", "Response", "P95", "Turnaround", "CPU %"), [
            (r["algorithm"], number(r["score"], 6), number(r["waiting"]), number(r["response"]),
             number(r["p95_response"]), number(r["turnaround"]), number(r["utilization"] * 100))
            for r in workload["comparison"]["results"]])
        table(("Policy", "Throughput (jobs/tick)", "Starvation", "PID switches"), [
            (r["algorithm"], number(r["throughput"], 6), number(r["starvation"], 0), r["context_switches"])
            for r in workload["comparison"]["results"]])
        heading("CONTROLLER OVERHEAD / THIS EXECUTION")
        table(("Controller", "Reviews", "Mean us", "P99 us", "Max us", "Total ms"), [
            (name, r["overhead"]["reviews"], number(r["overhead"]["decision_mean_us"]),
             number(r["overhead"]["decision_p99_us"]), number(r["overhead"]["decision_max_us"]),
             number(r["overhead"]["controller_total_ms"]))
            for name, r in workload["policies"].items() if "overhead" in r])
        print("Static-policy controller overhead: N/A. Dispatch overhead is not measured by this report.")
        print("Completion-time percentage: N/A; no physical ms-per-tick mapping for demo inputs.")
        for name, result in workload["policies"].items():
            if result["policy_transitions"]:
                table(("Switch tick", "From", "To", "Reason"), [
                    (e["effective_tick"], e["from_policy"], e["to_policy"], e["reason"])
                    for e in result["policy_transitions"]])
            if details:
                heading(f"PROCESS METRICS / {name}")
                table(("PID", "Arrival", "CPU", "Priority", "Waiting", "Response", "Turnaround"), [
                    (p["pid"], p["arrival_time"], p["burst_time"], p["priority"], p["waiting_time"],
                     p["response_time"], p["turnaround_time"]) for p in result["processes"]])


def latency(report):
    heading(f"FRESH CONTROLLER OVERHEAD / {report['suite'].upper()}")
    print(f"Model: {report['model']}")
    print(f"Selected / available workloads: {report['selected_workloads']} / {report['available_workloads']}"
          f" | Completed runs: {report['completed_runs']} | Timeouts: {len(report['failures'])}")
    if report["suite"] == "azure":
        print("Timing cohort: previously completed development workloads; the final holdout is untouched.")
    table(("Workload", "Runs", "Reviews", "Mean us", "P99 us", "Max us", "Total ms"), [
        (r["workload_id"], f"{r['completed_runs']}/{r['requested_runs']}", r["timing"]["reviews"],
         number(r["timing"]["decision_mean_us"]), number(r["timing"]["decision_p99_us"]),
         number(r["timing"]["decision_max_us"]), number(r["timing"]["controller_total_ms"])) for r in report["workloads"]])
    pooled = report["pooled"]
    table(("Pooled measurement", "Value", "Unit"), [
        ("Mean / review", number(pooled["decision_mean_us"]), "us"),
        ("Median / review", number(pooled["decision_p50_us"]), "us"),
        ("P95 / review", number(pooled["decision_p95_us"]), "us"),
        ("P99 / review", number(pooled["decision_p99_us"]), "us"),
        ("Maximum observed review", number(pooled["decision_max_us"]), "us"),
        ("Accumulated controller time", number(pooled["controller_total_ms"]), "ms"),
        ("Simulated completion time", number(pooled["makespan_ticks"], 0), "ticks (ms for Azure)"),
        ("CPU demand excluding idle", number(pooled["cpu_proxy_ticks"], 0), "ticks (ms for Azure)"),
        ("Controller / simulated completion", number(pooled["controller_vs_makespan_percent"], 6), "%"),
        ("Controller / CPU proxy", number(pooled["controller_vs_cpu_proxy_percent"], 6), "%"),
        ("Python simulation wall time", number(pooled["python_simulation_wall_ms"]), "ms"),
        ("Controller / Python wall time", number(pooled["controller_share_python_wall_percent"]), "%")])
    print("Only Azure has 1 tick = 1 ms. These ratios are illustrative budgets, not measured process slowdown.")
    print("Host overhead is not added to simulator time. P99 is not a hard maximum.")
    print("Scope: features, predictions, margin, guards and switch updates; excludes model load, dispatch and UI.")
    if report["failures"]:
        print("Timing totals include completed runs only; partial timed-out runs are excluded.")
        table(("Workload", "Status", "Reason"), [(r["workload_id"], r["status"], r["reason"]) for r in report["failures"]])


def bakeoff(report):
    heading("OFFLINE-REPLAY MODEL COMPARISON / SAVED RESULTS")
    results = report["results"]
    table(("Model", "Validation cost", "Locked cost", "Action match %", "P99 overhead ms", "Selected"), [
        (name, number(r["validation_realized_cost"], 6), number(r["locked_test_realized_cost"], 6),
         number(r["action_selection_accuracy"] * 100, 2), number(r["decision_p99_ms"], 6), "Yes" if r["selected"] else "No")
        for name, r in results["model_comparison"].items()])
    heading("OVERHEAD SCOPE")
    print("Saved per-model decision P99 shown above. Cumulative controller overhead: not recorded.")
    print("This is a separate replay prototype, not the original-v5 scheduling cohort.")
    g = results["gates"]
    print(f"Locked traces: {g['locked_test_trace_count']} / {g['minimum_locked_test_trace_count']} required"
          f" | Status: {g['status']} | No new fitting or bake-off performed.")
    print(f"Source: {report['source']}")


def print_report(kind, report, details=False):
    {"azure": azure, "azure_retrained": azure, "synthetic": synthetic,
     "demo": lambda r: demo(r, details), "latency": latency, "bakeoff": bakeoff}[kind](report)
    if "fresh_overhead" in report:
        latency(report["fresh_overhead"])
    print("\n-- = not measured / not available. Use --json for full records and provenance.")
