import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from autoscheduler.cli import build_parser
from autoscheduler.demo import run_demo


class FakeRunner:
    def __init__(self):
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append((command, kwargs))
        return 0


class DemoTests(unittest.TestCase):
    def run_menu(self, choices, root, runner=None, no_color=True):
        answers = iter(choices)
        output = io.StringIO()
        runner = runner or FakeRunner()
        run_demo(
            no_color=no_color,
            root=root,
            input_fn=lambda prompt="": next(answers),
            output=output,
            runner=runner,
        )
        return output.getvalue(), runner

    def write_json(self, root, relative_path, value):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_parser_accepts_demo_and_no_color(self):
        arguments = build_parser().parse_args(["demo", "--no-color"])

        self.assertEqual(arguments.command, "demo")
        self.assertTrue(arguments.no_color)

    def test_exit_and_invalid_selection_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            text, runner = self.run_menu(["invalid", "0"], Path(directory))

        self.assertIn("Invalid selection", text)
        self.assertIn("Demo closed", text)
        self.assertEqual(runner.commands, [])

    def test_compare_uses_defaults_and_accepts_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "results/six_policy/model.joblib"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"model")
            runner = FakeRunner()

            self.run_menu(["3", "", "", "3", "interactive", "77", "0"], root, runner)

        first = runner.commands[0][0]
        second = runner.commands[1][0]
        self.assertEqual(first[:3], [sys.executable, str(root / "main.py"), "compare"])
        self.assertIn("mixed", first)
        self.assertIn("42", first)
        self.assertIn("interactive", second)
        self.assertIn("77", second)

    def test_live_command_prefers_project_virtualenv_python(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "results/six_policy/model.joblib"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"model")
            project_python = root / ".venv/bin/python"
            project_python.parent.mkdir(parents=True)
            project_python.touch()
            runner = FakeRunner()

            self.run_menu(["3", "", "", "0"], root, runner)

        self.assertEqual(runner.commands[0][0][0], str(project_python))

    def test_invalid_profile_and_seed_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "results/six_policy/model.joblib"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"model")
            runner = FakeRunner()

            text, runner = self.run_menu(["3", "wrong", "seed", "0"], root, runner)

        command = runner.commands[0][0]
        self.assertIn("mixed", command)
        self.assertIn("42", command)
        self.assertIn("Using default profile", text)
        self.assertIn("Using default seed", text)

    def test_missing_artifact_prints_recovery_command(self):
        with tempfile.TemporaryDirectory() as directory:
            text, _ = self.run_menu(["4", "0"], Path(directory))

        self.assertIn("Unavailable", text)
        self.assertIn("python main.py evaluate", text)

    def test_saved_result_sections_render_evidence_without_changing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            static = self.write_json(root, "results/six_policy/summary.json", {
                "samples": 1000,
                "static_policies": ["SJF", "SRTF", "Round Robin"],
                "mean_static_scores": {"SJF": 0.21, "SRTF": 0.17, "Round Robin": 0.13},
                "mean_adaptive_score": 0.131,
                "best_static_algorithm": "Round Robin",
                "adaptive_statistically_beats_static": False,
                "eligible_for_next_adaptive_phase": False,
            })
            self.write_json(root, "results/six_policy/full_latency/latency_summary.json", {
                "seed": 3030,
                "samples_per_profile": 20,
                "gate_p99_ms": 10.0,
                "passes_latency_gate": {"Round Robin": True, "Adaptive": True},
                "recommended_policy": "Round Robin",
                "latency": {
                    "Round Robin": {"large": {"p99_ms": 0.061}},
                    "Adaptive": {"large": {"p99_ms": 6.551}},
                },
            })
            self.write_json(root, "results/six_policy/dynamic/dynamic_summary.json", {
                "seed": 2026,
                "traces": 1000,
                "mean_static_scores": {"Round Robin": 0.11},
                "weighted_score_gate": True,
                "p95_response_gate": False,
                "latency_gate": False,
                "eligible": False,
            })
            self.write_json(root, "results/rr_srtf_benefit/summary.json", {
                "seed": 4040,
                "samples": 1000,
                "mean_rr_score": 0.112,
                "mean_benefit_score": 0.037,
                "relative_improvement_vs_rr": 0.669,
                "confidence_gate": True,
                "full_latency_gate": True,
                "eligible": True,
                "recommended_policy": "Benefit selector",
            })
            self.write_json(root, "results/mlfq_baseline/summary.json", {
                "seed": 6060,
                "samples": 1000,
                "rr_quantum": 1,
                "policies": {
                    "Tuned RR": {"mean_score": 0.125},
                    "SRTF": {"mean_score": 0.175},
                    "RR20-SRTF": {"mean_score": 0.089},
                    "MLFQ": {"mean_score": 0.131},
                },
                "score_gate": False,
                "fairness_gate": False,
                "latency_gate": {"RR20-SRTF": {"passes_gate": True}},
                "recommended_policy": "RR20-SRTF",
            })
            before = static.read_bytes()

            text, _ = self.run_menu(["4", "5", "6", "7", "8", "0"], root)

            self.assertEqual(static.read_bytes(), before)

        self.assertIn("Round Robin", text)
        self.assertIn("P95 response gate", text)
        self.assertIn("Benefit selector", text)
        self.assertIn("RR20-SRTF", text)
        self.assertIn("6.551", text)

    def test_roadmap_is_read_only_and_color_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            text, runner = self.run_menu(["9", "0"], Path(directory), no_color=True)

        self.assertIn("NOT IMPLEMENTED", text)
        self.assertIn("{5, 10, 20, 40, never}", text)
        self.assertNotIn("\x1b[", text)
        self.assertEqual(runner.commands, [])

    def test_guided_tour_can_stop_without_running_expensive_experiments(self):
        with tempfile.TemporaryDirectory() as directory:
            text, runner = self.run_menu(["1", "q", "0"], Path(directory))

        self.assertIn("CLASSICAL SCHEDULERS", text)
        self.assertEqual(len(runner.commands), 1)
        self.assertEqual(runner.commands[0][0][2:], [])

    def test_main_demo_command_exits_cleanly(self):
        completed = __import__("subprocess").run(
            [sys.executable, "main.py", "demo", "--no-color"],
            input="0\n",
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("AUTOSCHEDULER EXPERIMENT DEMO", completed.stdout)
        self.assertIn("Demo closed", completed.stdout)
        self.assertNotIn("\x1b[", completed.stdout)

    def test_live_scheduler_race_animates_six_policies_and_reports_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            answers = iter(["10", "", "", "0"])
            output = io.StringIO()

            run_demo(
                no_color=True,
                root=Path(directory),
                input_fn=lambda prompt="": next(answers),
                output=output,
                runner=FakeRunner(),
                sleep_fn=lambda seconds: None,
            )

        text = output.getvalue()
        self.assertIn("LIVE SCHEDULER RACE", text)
        for policy in ("FCFS", "SJF", "SRTF", "Round Robin", "Priority", "Priority RR"):
            self.assertIn(policy, text)
        self.assertIn("metrics use complete timeline", text)
        self.assertIn("Winner", text)


if __name__ == "__main__":
    unittest.main()
