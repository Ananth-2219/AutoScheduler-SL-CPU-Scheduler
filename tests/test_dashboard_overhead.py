"""Dashboard timing must match the displayed run, cohort, and time units."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class DashboardOverheadTests(unittest.TestCase):
    def test_demo_reports_measured_controller_time_and_separate_switch_charge(self):
        from dashboard.adapter import simulation
        simulation.cache_clear()
        result = simulation("dynamic_response_advantage", "Dynamic ML (v5)")
        timing = result["overhead"]
        self.assertAlmostEqual(timing["controller_total_ms"],
                               sum(d["transition_ms"] for d in result["routing_decisions"]))
        self.assertEqual(timing["reviews"], len(result["routing_decisions"]))
        self.assertEqual(timing["makespan_ticks"], result["metrics"]["makespan"])
        self.assertIsNone(timing["controller_vs_makespan_percent"])
        self.assertGreater(timing["controller_share_python_wall_percent"], 0)
        self.assertLessEqual(timing["controller_share_python_wall_percent"], 100)
        static = simulation("mixed_io", "Priority RR")
        self.assertIsNone(static["overhead"])
        self.assertAlmostEqual(static["switch_overhead_percent"],
                               100 * static["metrics"]["context_switch_time"] / static["metrics"]["makespan"])

    def test_missing_or_stale_snapshot_never_fabricates_zero_overhead(self):
        from dashboard.overhead import load_snapshot
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timing.json"
            self.assertEqual(load_snapshot(path)["status"], "unavailable")
            path.write_text(json.dumps({"schema_version": 1, "fingerprints": {"missing": "old"}, "cohorts": {"fake": 0}}))
            with patch("dashboard.overhead.fingerprints", return_value={"missing": "new"}):
                report = load_snapshot(path)
            self.assertEqual(report["status"], "stale")
            self.assertEqual(report["cohorts"], {})
            path.write_text("broken json")
            self.assertEqual(load_snapshot(path)["status"], "unavailable")

    def test_valid_snapshot_is_served_without_replaying_workloads(self):
        from dashboard.overhead import load_snapshot
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timing.json"
            snapshot = {"schema_version": 1, "fingerprints": {"input": "abc"},
                        "status": "measured", "cohorts": {"azure_original": {"entries": []}}}
            path.write_text(json.dumps(snapshot))
            with patch("dashboard.overhead.fingerprints", return_value={"input": "abc"}), \
                 patch("autoscheduler.review_metrics.latency_report", side_effect=AssertionError("No replay on load")):
                self.assertEqual(load_snapshot(path), snapshot)

    def test_original_model_can_be_timed_on_the_retrained_six_workload_cohort(self):
        from autoscheduler.review_metrics import azure_report, latency_report
        report = latency_report("azure", model_name="original", azure_cohort="retrained",
                                repeats=1, warmups=0, limit=1)
        expected = azure_report(True)["scheduling"]["common_workload_ids"]
        self.assertEqual(report["available_workloads"], 6)
        self.assertIn(report["workloads"][0]["workload_id"], expected)
        self.assertEqual(report["pooled"]["ms_per_tick"], 1)
        self.assertAlmostEqual(report["pooled"]["controller_vs_makespan_percent"],
                               100 * report["pooled"]["controller_total_ms"] / report["pooled"]["makespan_ticks"])

    def test_snapshot_verifies_scheduling_outcomes_not_just_ids(self):
        from dashboard.overhead import verify_azure_replay
        report = {"workloads": [{"workload_id": "x", "status": "COMPLETE",
                                 "schedule_metrics": {"avg_waiting_ms": 2, "avg_response_ms": 1,
                                                      "avg_turnaround_ms": 3}}]}
        saved = [{"workload_id": "x", "policy": "Original v5", "status": "COMPLETE",
                  "avg_waiting_ms": 2, "avg_response_ms": 1, "avg_turnaround_ms": 3}]
        verify_azure_replay(report, saved, "Original v5")
        report["workloads"][0]["schedule_metrics"]["avg_waiting_ms"] = 200
        with self.assertRaisesRegex(ValueError, "scheduling outcome"):
            verify_azure_replay(report, saved, "Original v5")

    def test_catalog_exposes_timing_separately_from_historical_results(self):
        from fastapi.testclient import TestClient
        from dashboard.app import app
        with TestClient(app) as client:
            result = client.get("/api/catalog").json()
            self.assertIn("controller_overhead", result)
            self.assertIn("status", result["controller_overhead"])
            self.assertIn("external", result["real_source_dynamic"])


if __name__ == "__main__":
    unittest.main()
