import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def event(timestamp_ms, pid, event_type, priority=120, previous_state=None):
    return {
        "timestamp_ns": timestamp_ms * 1_000_000,
        "cpu": 0,
        "pid": pid,
        "type": event_type,
        "priority": priority,
        "previous_state": previous_state,
        "ready_count": None,
        "wakeup_source": None,
    }


TRACE = {
    "schema_version": 1,
    "metadata": {
        "trace_id": "feature-fixture",
        "source": "linux",
        "application": "probe",
        "workload_family": "wakeup",
        "capture_session": "fixture-session",
        "truncated": False,
    },
    "events": [
        event(0, 1, "arrival"),
        event(10, 1, "switch_in"),
        event(20, 1, "switch_out", previous_state="S"),
        event(30, 1, "wakeup"),
        event(40, 1, "switch_in"),
        event(60, 1, "switch_out", previous_state="Z"),
        event(61, 1, "exit"),
        event(80, 2, "arrival", priority=130),
    ],
    "processes": [
        {"pid": 1, "arrival_ns": 0, "completion_ns": 61_000_000, "priority": 120,
         "parent_pid": None, "cgroup": None, "application_family": "probe", "truncated": False},
        {"pid": 2, "arrival_ns": 80_000_000, "completion_ns": None, "priority": 130,
         "parent_pid": None, "cgroup": None, "application_family": "probe", "truncated": True},
    ],
    "outcomes": [],
}


class RealFeatureTests(unittest.TestCase):
    def test_features_use_only_events_before_decision(self):
        from autoscheduler.real_features import FEATURE_NAMES, extract_features_at

        first = extract_features_at(TRACE, 50_000_000, 50)
        altered = json.loads(json.dumps(TRACE))
        altered["events"].append(event(90, 99, "wakeup", priority=1))
        second = extract_features_at(altered, 50_000_000, 50)

        self.assertEqual(tuple(first), FEATURE_NAMES)
        self.assertEqual(first, second)
        self.assertEqual(first["arrivals_seen"], 1.0)
        self.assertEqual(first["wakeups"], 1.0)
        self.assertEqual(first["running_count"], 1.0)
        self.assertEqual(first["wait_mean_ms"], 10.0)
        self.assertEqual(first["cpu_busy_fraction"], 0.4)

    def test_rows_and_cli_write_only_declared_features(self):
        from autoscheduler.real_features import FEATURE_NAMES, extract_feature_rows, write_feature_rows

        rows = extract_feature_rows([TRACE], initial_observation_ms=20, feature_window_ms=20,
                                    decision_interval_ms=20)
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(set(rows[0]), {"trace_id", "application", "workload_family", "scenario",
                                        "configuration_id", "capture_session", "decision_timestamp_ns",
                                        *FEATURE_NAMES})
        self.assertEqual(rows[0]["scenario"], rows[0]["trace_id"])
        self.assertEqual(rows[0]["configuration_id"], rows[0]["trace_id"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traces = root / "traces.jsonl"
            output = root / "features.csv"
            traces.write_text(json.dumps(TRACE) + "\n", encoding="utf-8")
            write_feature_rows(rows, output)
            completed = subprocess.run(
                [sys.executable, "main.py", "real-features", str(traces), "--output", str(output)],
                check=True, capture_output=True, text=True,
            )
            self.assertIn("Feature rows:", completed.stdout)
            self.assertIn("arrivals_seen", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
