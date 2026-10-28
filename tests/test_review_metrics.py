"""Read-only reporting must preserve cohort denominators and timing units."""
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from autoscheduler.review_metrics import (
    aggregate_rows, azure_report, compare, demo_report, latency_totals,
    prediction_report, synthetic_report,
)


class ReviewMetricTests(unittest.TestCase):
    def test_common_complete_means_exclude_failures_and_missing_policies(self):
        rows = [
            dict(workload_id="one", policy="A", status="COMPLETE", value=2),
            dict(workload_id="one", policy="B", status="COMPLETE", value=4),
            dict(workload_id="two", policy="A", status="COMPLETE", value=100),
            dict(workload_id="two", policy="B", status="TIMEOUT", value=None),
            dict(workload_id="three", policy="A", status="COMPLETE", value=300),
        ]
        report = aggregate_rows(rows, ("A", "B"), ("value",))
        self.assertEqual(report["completed_workloads"], 1)
        self.assertEqual(report["selected_workloads"], 3)
        self.assertEqual(report["means"]["A"]["value"], 2)
        self.assertEqual(len(report["failures"]), 1)
        self.assertEqual(report["incomplete_workload_ids"], ["three", "two"])

    def test_duplicate_policy_rows_are_rejected(self):
        row = dict(workload_id="one", policy="A", status="COMPLETE", value=1)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            aggregate_rows([row, row], ("A",), ("value",))

    def test_comparison_matches_dashboard_ties_direction_and_zero_reference(self):
        self.assertEqual(compare(0, 0)["status"], "tie")
        self.assertEqual(compare(5, 10)["percent"], 50)
        self.assertEqual(compare(5, 10, higher=True)["winner"], "baseline")
        self.assertIsNone(compare(-1, 0)["percent"])
        self.assertEqual(compare(None, 10)["status"], "unmeasured")

    def test_latency_uses_sum_not_p99_and_does_not_assign_synthetic_ms(self):
        decisions = [SimpleNamespace(transition_ms=1, accepted=True),
                     SimpleNamespace(transition_ms=3, accepted=False)]
        report = latency_totals(decisions, makespan=1000, cpu_ticks=100, wall_ms=10, tick_ms=1)
        self.assertEqual(report["controller_total_ms"], 4)
        self.assertEqual(report["controller_vs_makespan_percent"], .4)
        self.assertEqual(report["controller_vs_cpu_proxy_percent"], 4)
        self.assertEqual(report["controller_share_python_wall_percent"], 40)
        self.assertEqual(report["decision_mean_us"], 2000)
        self.assertIsNone(latency_totals([], 100, 50, 1, None)["controller_vs_makespan_percent"])

    def test_azure_means_match_dashboard_without_reading_displayed_means(self):
        root = Path(__file__).resolve().parents[1]
        expected = json.loads((root / "results/real_source_dynamic_review_20261020/dashboard.json").read_text())["external"]
        report = azure_report()
        self.assertEqual(report["scheduling"]["completed_workloads"], 12)
        self.assertEqual(report["scheduling"]["selected_workloads"], 17)
        self.assertEqual(len(report["scheduling"]["failures"]), 8)
        for policy in ("Dynamic v5", "Tuned MLFQ"):
            for key in ("weighted_score", "avg_waiting_ms", "p95_response_ms"):
                self.assertAlmostEqual(report["scheduling"]["means"][policy][key], expected["metrics"][policy][key])
        self.assertEqual(report["decision_totals"]["reviews"], 25132)

    def test_retrained_report_keeps_its_six_workload_cohort_separate(self):
        report = azure_report(retrained=True)
        self.assertEqual(report["scheduling"]["completed_workloads"], 6)
        self.assertEqual(report["accepted_switch_totals"]["Azure-retrained v5"], 2)
        self.assertEqual(report["scheduling"]["means"]["Azure-retrained v5"],
                         report["scheduling"]["means"]["Tuned MLFQ"])

    def test_synthetic_report_recomputes_csv_means(self):
        report = synthetic_report(5)
        self.assertEqual(report["workloads"], 240)
        self.assertAlmostEqual(report["means"]["policy_cost"]["score"], .13588730490040574)

    def test_demo_uses_actual_backend_result(self):
        report = demo_report("dynamic_response_advantage", "Dynamic ML (v5)")
        result = report["workloads"]["dynamic_response_advantage"]["policies"]["Dynamic ML (v5)"]
        self.assertEqual(result["metrics"]["makespan"], 254)
        self.assertEqual([e["effective_tick"] for e in result["policy_transitions"]], [22, 52])
        self.assertEqual(len(result["processes"]), 14)

    def test_regression_metrics_are_fresh_inference_without_fitting(self):
        with patch("sklearn.tree.DecisionTreeRegressor.fit", side_effect=AssertionError("No fitting")):
            report = prediction_report(False)
        self.assertEqual(report["splits"]["test"]["decision_rows"], 72)
        self.assertAlmostEqual(report["splits"]["test"]["mae"], .012602638025133114)

    def test_latency_command_measures_decisions_without_charging_simulated_time(self):
        from autoscheduler.review_metrics import latency_report
        report = latency_report("demo", repeats=1, warmups=0, limit=1)
        row = report["workloads"][0]
        self.assertEqual(row["completed_runs"], 1)
        self.assertEqual(row["timing"]["reviews"], 2)
        self.assertEqual(row["timing"]["makespan_ticks"], 21)
        self.assertGreater(row["timing"]["controller_total_ms"], 0)
        self.assertIsNone(row["timing"]["controller_vs_makespan_percent"])

    def test_invalid_replay_budgets_are_rejected(self):
        from autoscheduler.review_metrics import latency_report
        for kwargs in ({"repeats": 0}, {"limit": 0}, {"warmups": -1}, {"timeout_seconds": 0}):
            with self.assertRaises(ValueError):
                latency_report("demo", **kwargs)

    def test_timeout_is_retained_and_cannot_pass_latency_gate(self):
        import signal
        from autoscheduler.review_metrics import latency_report
        before = signal.getsignal(signal.SIGALRM)
        with patch("autoscheduler.dynamic.run_dynamic", side_effect=TimeoutError("cap")):
            report = latency_report("demo", repeats=1, warmups=0, limit=1)
        self.assertEqual(report["completed_runs"], 0)
        self.assertEqual(report["failures"][0]["status"], "TIMEOUT")
        self.assertIsNone(report["pooled"]["decision_p99_us"])
        self.assertFalse(report["complete_coverage_p99_lt_10ms"])
        self.assertEqual(signal.getsignal(signal.SIGALRM), before)
        from autoscheduler.metric_tables import print_report
        output = StringIO()
        with redirect_stdout(output):
            print_report("latency", report)
        self.assertIn("partial timed-out runs are excluded", output.getvalue())

    def test_terminal_azure_report_has_tables_and_matching_cohort_overhead(self):
        from autoscheduler.metric_tables import print_report
        report = azure_report()
        output = StringIO()
        with redirect_stdout(output):
            print_report("azure", report)
        text = output.getvalue()
        self.assertIn("SCHEDULING PERFORMANCE", text)
        self.assertIn("CONTROLLER OVERHEAD", text)
        self.assertIn("12 / 17", text)
        self.assertIn("4,254.610", text)
        self.assertIn("not recorded", text)
        self.assertNotIn("metric_sample_counts", text)
        self.assertLess(len(text.splitlines()), 100)

    def test_demo_overhead_comes_from_actual_routing_records(self):
        report = demo_report("short_jobs", "Dynamic ML (v5)")
        result = report["workloads"]["short_jobs"]["policies"]["Dynamic ML (v5)"]
        expected = sum(d["transition_ms"] for d in result["routing_decisions"])
        self.assertEqual(result["overhead"]["controller_total_ms"], expected)
        self.assertIsNone(result["overhead"]["controller_vs_makespan_percent"])

    def test_retrained_overhead_uses_its_own_saved_runs(self):
        report = azure_report(retrained=True)
        self.assertEqual(set(report["overhead"]), {"Original v5", "Azure-retrained v5", "Tuned MLFQ"})
        self.assertIsNone(report["overhead"]["Tuned MLFQ"]["max_workload_p99_us"])
        self.assertGreater(report["overhead"]["Azure-retrained v5"]["max_workload_p99_us"], 0)

    def test_static_only_demo_can_render_without_fabricating_controller_time(self):
        from autoscheduler.metric_tables import print_report
        report = demo_report("short_jobs", "FCFS")
        output = StringIO()
        with redirect_stdout(output):
            print_report("demo", report, details=True)
        self.assertIn("Static-policy controller overhead: N/A", output.getvalue())
        self.assertNotIn("overhead", report["workloads"]["short_jobs"]["policies"]["FCFS"])


if __name__ == "__main__":
    unittest.main()
