"""Interactive terminal front-end for AutoScheduler experiment demos."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from autoscheduler.workloads import PROFILES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESET = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
AMBER = "\033[33m"


def run_demo(
    *,
    no_color: bool = False,
    root: Path = PROJECT_ROOT,
    input_fn=input,
    output=sys.stdout,
    runner=subprocess.run,
    sleep_fn=time.sleep,
) -> None:
    """Run numbered presentation menu without changing research artifacts."""
    color = not no_color and bool(getattr(output, "isatty", lambda: False)())

    def emit(text: str = "") -> None:
        print(text, file=output)

    def styled(text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if color else text

    def ask(prompt: str) -> str:
        output.write(prompt)
        output.flush()
        try:
            return input_fn("").strip()
        except (EOFError, KeyboardInterrupt, StopIteration):
            return "q"

    def title(text: str) -> None:
        emit()
        emit(styled("=" * 72, CYAN))
        emit(styled(text, CYAN))
        emit(styled("=" * 72, CYAN))

    def status(label: str, value) -> None:
        if isinstance(value, bool):
            word = "PASS" if value else "FAIL"
            emit(f"{label:<31} {styled(word, GREEN if value else AMBER)}")
        else:
            emit(f"{label:<31} {value}")

    def unavailable(relative: str, command: str) -> None:
        emit(styled("Unavailable", AMBER))
        emit(f"Missing: {relative}")
        emit("Generate with:")
        emit(f"  {command}")

    def load(relative: str, command: str, *, report_missing: bool = True):
        path = root / relative
        if not path.exists():
            if report_missing:
                unavailable(relative, command)
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            emit(styled("Unavailable", AMBER))
            emit(f"Cannot read {relative}: {error}")
            emit(f"Regenerate with: {command}")
            return None

    def run_cli(arguments: list[str]) -> None:
        command = [_project_python(root), str(root / "main.py"), *arguments]
        result = runner(command, cwd=root)
        return_code = result if isinstance(result, int) else result.returncode
        if return_code:
            emit(styled(f"Command exited with status {return_code}.", AMBER))

    def classical() -> None:
        title("CLASSICAL SCHEDULERS — LIVE")
        run_cli([])

    def workload_inputs() -> tuple[str, int]:
        profile = "mixed"
        seed = 42
        entered_profile = ask(
            "Profile [interactive/batch/cpu_intensive/io_intensive/mixed] "
            "(mixed): "
        )
        if entered_profile:
            if entered_profile in PROFILES:
                profile = entered_profile
            else:
                emit("Using default profile: mixed")
        entered_seed = ask("Seed (42): ")
        if entered_seed:
            try:
                seed = int(entered_seed)
            except ValueError:
                emit("Using default seed: 42")
        return profile, seed

    def comparison(*, prompt: bool = True) -> None:
        title("SIX-POLICY ADAPTIVE COMPARISON — LIVE")
        model = root / "results/six_policy/model.joblib"
        if not model.exists():
            unavailable(
                "results/six_policy/model.joblib",
                "python main.py train --model results/six_policy/model.joblib "
                "--dataset results/six_policy/training.csv",
            )
            return
        profile, seed = workload_inputs() if prompt else ("mixed", 42)
        run_cli([
            "compare", "--profile", profile, "--seed", str(seed),
            "--model", str(model),
        ])

    def race() -> None:
        from autoscheduler.evaluation import compare_algorithms, score_results
        from autoscheduler.workloads import generate_workload

        title("LIVE SCHEDULER RACE")
        profile, seed = workload_inputs()
        workload = generate_workload(profile, seed)
        priority_rr_config = None
        metadata_path = root / "results/six_policy/model.json"
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                priority_rr_config = metadata.get("priority_rr_config")
            except (OSError, json.JSONDecodeError):
                pass
        results = compare_algorithms(workload.processes, priority_rr_config)
        scores = score_results(results)

        emit(
            f"Workload: {profile} | seed={seed} | "
            f"processes={len(workload.processes)}"
        )
        emit("Timeline playback:")
        for policy, result in results.items():
            emit(styled(policy, CYAN))
            output.write("  ")
            column = 2
            visible_timeline = result.timeline[:24]
            for pid, start, end in visible_timeline:
                token = f"{pid}[{start}-{end}] "
                if column + len(token) > 72:
                    output.write("\n  ")
                    column = 2
                output.write(token)
                output.flush()
                column += len(token)
                sleep_fn(0.02)
            output.write("\n")
            hidden = len(result.timeline) - len(visible_timeline)
            if hidden:
                emit(f"  ... {hidden} more events; metrics use complete timeline")

        emit()
        emit("Policy               Wait   Response  Turnaround   Score")
        for policy, result in results.items():
            emit(
                f"{policy:<20} {result.avg_waiting_time:>6.2f} "
                f"{result.avg_response_time:>10.2f} "
                f"{result.avg_turnaround_time:>11.2f} {scores[policy]:>7.3f}"
            )
        winner = min(scores, key=scores.get)
        emit()
        emit(styled(f"Winner: {winner} (weighted score {scores[winner]:.3f})", GREEN))

    def six_policy() -> None:
        title("SIX-POLICY EVALUATION")
        relative = "results/six_policy/summary.json"
        summary = load(
            relative,
            "python main.py evaluate --model results/six_policy/model.joblib "
            "--output results/six_policy",
        )
        if not summary:
            return
        status("Seed", summary.get("seed", "2026 (standard run)"))
        status("Workloads", summary.get("samples", "not recorded"))
        emit("Policies:")
        scores = summary.get("mean_static_scores", {})
        for policy in summary.get("static_policies", scores):
            score = scores.get(policy)
            emit(f"  {policy:<20} {score:.6f}" if isinstance(score, (int, float)) else f"  {policy}")
        status("Adaptive mean score", _number(summary.get("mean_adaptive_score")))
        status("Best static policy", summary.get("best_static_algorithm", "not recorded"))
        status("Statistical gate", summary.get("adaptive_statistically_beats_static", False))
        status("Adaptive expansion gate", summary.get("eligible_for_next_adaptive_phase", False))
        latency = load(
            "results/six_policy/full_latency/latency_summary.json",
            "python main.py latency --model results/six_policy/model.joblib "
            "--score-summary results/six_policy/summary.json "
            "--output results/six_policy/full_latency",
            report_missing=False,
        )
        if latency:
            status("Latency gate", all(latency.get("passes_latency_gate", {}).values()))
            status("Recommended policy", latency.get("recommended_policy", "not recorded"))
        emit(f"Source: {relative}")

    def dynamic() -> None:
        title("CHANGING-WORKLOAD ROUTER")
        relative = "results/six_policy/dynamic/dynamic_summary.json"
        summary = load(
            relative,
            "python main.py dynamic-evaluate --model "
            "results/six_policy/dynamic_model.joblib "
            "--output results/six_policy/dynamic",
        )
        if not summary:
            return
        status("Seed", summary.get("seed", "not recorded"))
        status("Traces", summary.get("traces", "not recorded"))
        emit("Static mean scores:")
        for policy, score in summary.get("mean_static_scores", {}).items():
            emit(f"  {policy:<20} {score:.6f}")
        status("Weighted score gate", summary.get("weighted_score_gate", False))
        status("P95 response gate", summary.get("p95_response_gate", False))
        status("Latency gate", summary.get("latency_gate", False))
        status("Eligible", summary.get("eligible", False))
        emit(f"Source: {relative}")

    def benefit() -> None:
        title("RR-VERSUS-SRTF BENEFIT REGRESSOR")
        relative = "results/rr_srtf_benefit/summary.json"
        summary = load(relative, "python main.py benefit-evaluate")
        if not summary:
            return
        status("Seed", summary.get("seed", "not recorded"))
        status("Workloads", summary.get("samples", "not recorded"))
        status("Tuned RR score", _number(summary.get("mean_rr_score")))
        status("Benefit selector score", _number(summary.get("mean_benefit_score")))
        improvement = summary.get("relative_improvement_vs_rr")
        status("Relative improvement", f"{improvement:.2%}" if isinstance(improvement, (int, float)) else "not recorded")
        status("Confidence gate", summary.get("confidence_gate", False))
        status("Latency gate", summary.get("full_latency_gate", summary.get("latency_gate", False)))
        status("Eligible", summary.get("eligible", False))
        status("Recommended policy", summary.get("recommended_policy", "not recorded"))
        emit(f"Source: {relative}")

    def mlfq() -> None:
        title("MLFQ AND FIXED RR20-SRTF BASELINE")
        relative = "results/mlfq_baseline/summary.json"
        summary = load(relative, "python main.py mlfq-evaluate && python main.py mlfq-latency")
        if not summary:
            return
        status("Seed", summary.get("seed", "not recorded"))
        status("Workloads", summary.get("samples", "not recorded"))
        status("RR quantum", summary.get("rr_quantum", "not recorded"))
        emit("Mean weighted scores:")
        for policy, metrics in summary.get("policies", {}).items():
            score = metrics.get("mean_score")
            emit(f"  {policy:<20} {_number(score)}")
        status("MLFQ score gate", summary.get("score_gate", False))
        status("MLFQ fairness gate", summary.get("fairness_gate", False))
        latency_gate = summary.get("latency_gate", False)
        if isinstance(latency_gate, dict):
            latency_gate = all(
                item.get("passes_gate", False) if isinstance(item, dict) else bool(item)
                for item in latency_gate.values()
            )
        status("Latency gate", latency_gate)
        status("Recommended policy", summary.get("recommended_policy", "not recorded"))
        emit("RR20-SRTF: RR quantum 1 until tick 20, then permanent SRTF.")
        emit(f"Source: {relative}")

    def latency() -> None:
        title("DECISION LATENCY")
        groups = (
            (
                "Six-policy benchmark",
                "results/six_policy/full_latency/latency_summary.json",
                "python main.py latency --model results/six_policy/model.joblib "
                "--score-summary results/six_policy/summary.json "
                "--output results/six_policy/full_latency",
            ),
            (
                "MLFQ baseline benchmark",
                "results/mlfq_baseline/latency_summary.json",
                "python main.py mlfq-latency",
            ),
        )
        for label, relative, command in groups:
            emit(styled(label, CYAN))
            summary = load(relative, command)
            if not summary:
                continue
            status("Seed", summary.get("seed", "not recorded"))
            status("Samples per profile", summary.get("samples_per_profile", "not recorded"))
            emit("P99 decision time (ms):")
            for policy, sizes in summary.get("latency", {}).items():
                values = "  ".join(
                    f"{size}={metrics.get('p99_ms', 0):.3f}"
                    for size, metrics in sizes.items()
                )
                emit(f"  {policy:<16} {values}")
            gates = summary.get("passes_latency_gate", summary.get("policy_gate", {}))
            passed = all(
                item.get("passes_gate", False) if isinstance(item, dict) else bool(item)
                for item in gates.values()
            ) if isinstance(gates, dict) and gates else False
            status("Strict P99 <10 ms", passed)
            if "recommended_policy" in summary:
                status("Recommended policy", summary["recommended_policy"])
            emit(f"Source: {relative}")
            emit()

    def roadmap() -> None:
        title("PLANNED ML SWITCH-TIME EXPERIMENT")
        emit(styled("NOT IMPLEMENTED", AMBER))
        emit("RR quantum stays fixed at 1.")
        emit("ML chooses one switch time: {5, 10, 20, 40, never}.")
        emit("Runtime features contain observed information only.")
        emit("Required gates:")
        emit("  - At least 1% lower score than best fixed switch time")
        emit("  - Paired 95% confidence interval entirely below zero")
        emit("  - Decision P99 strictly below 10 ms")

    def guided() -> None:
        sections = (classical, race, six_policy, dynamic, benefit, mlfq, latency, roadmap)
        for index, section in enumerate(sections):
            section()
            if index < len(sections) - 1:
                if ask("Press Enter to continue, or q to stop tour: ").lower() == "q":
                    break

    handlers = {
        "1": guided,
        "2": classical,
        "3": comparison,
        "4": six_policy,
        "5": dynamic,
        "6": benefit,
        "7": mlfq,
        "8": latency,
        "9": roadmap,
        "10": race,
    }

    while True:
        title("AUTOSCHEDULER EXPERIMENT DEMO")
        emit("1  Guided tour")
        emit("2  Classical schedulers live")
        emit("3  Six-policy adaptive comparison live")
        emit("4  Six-policy evaluation results")
        emit("5  Changing-workload router results")
        emit("6  RR-versus-SRTF benefit results")
        emit("7  MLFQ and RR20-SRTF results")
        emit("8  Latency results")
        emit("9  Planned ML switch-time experiment")
        emit("10 Live scheduler race")
        emit("0  Exit")
        choice = ask("Select: ").lower()
        if choice in {"0", "q"}:
            emit("Demo closed.")
            return
        handler = handlers.get(choice)
        if handler:
            handler()
        else:
            emit(styled("Invalid selection. Choose 0-10.", AMBER))


def _number(value) -> str:
    return f"{value:.6f}" if isinstance(value, (int, float)) else "not recorded"


def _project_python(root: Path) -> str:
    for candidate in (root / ".venv/bin/python", root / ".venv/Scripts/python.exe"):
        if candidate.exists():
            return str(candidate)
    return sys.executable
