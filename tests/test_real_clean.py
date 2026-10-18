import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _trace():
    return {
        "schema_version": 1,
        "metadata": {
            "trace_id": "knightnm-firefox-/home/knightnm/capture",
            "source": "linux",
            "source_url": "file:///home/knightnm/capture/trace.dat",
            "application": "firefox-esr",
            "workload_family": "firefox",
            "scenario": "firefox-tabs-3",
            "configuration_id": "firefox-tabs-3",
            "capture_session": "private-session",
            "machine_id": "BadraKali",
            "kernel_version": "6.19.0-kali",
            "capture_user": "knightnm",
            "command": ["/home/knightnm/autoscheduler/tools/run_firefox_probe.sh"],
            "affinity_cpu": 0,
            "trace_cpus": "all",
            "anonymized": False,
            "truncated": False,
        },
        "events": [
            {"timestamp_ns": 1, "cpu": 0, "pid": 41, "type": "arrival", "priority": 120,
             "previous_state": None, "ready_count": None, "wakeup_source": None},
            {"timestamp_ns": 2, "cpu": 0, "pid": 99, "type": "wakeup", "priority": 120,
             "previous_state": None, "ready_count": None, "wakeup_source": 41},
            {"timestamp_ns": 3, "cpu": 0, "pid": 99, "type": "exit", "priority": 120,
             "previous_state": None, "ready_count": None, "wakeup_source": 999},
        ],
        "processes": [
            {"pid": 41, "arrival_ns": 1, "completion_ns": 4, "priority": 120,
             "parent_pid": None, "cgroup": "/user.slice/knightnm", "application_family": "firefox-esr",
             "truncated": False},
            {"pid": 99, "arrival_ns": 2, "completion_ns": 3, "priority": 120,
             "parent_pid": 41, "cgroup": "/user.slice/knightnm", "application_family": "firefox-esr",
             "truncated": False},
        ],
        "outcomes": [{"command": "/home/knightnm/private-command"}],
    }


class RealTraceCleaningTests(unittest.TestCase):
    def test_cleaning_removes_identifiers_and_remaps_processes(self):
        from autoscheduler.real_clean import clean_traces
        from autoscheduler.real_traces import validate_trace

        cleaned = clean_traces([_trace()], "pilot-clean")

        self.assertEqual(cleaned[0]["metadata"]["trace_id"], "pilot-clean-trace-0001")
        self.assertEqual(cleaned[0]["metadata"]["application"], "firefox")
        self.assertTrue(cleaned[0]["metadata"]["anonymized"])
        self.assertNotIn("machine_id", cleaned[0]["metadata"])
        self.assertNotIn("source_url", cleaned[0]["metadata"])
        self.assertEqual([process["pid"] for process in cleaned[0]["processes"]], [1, 2])
        self.assertEqual(cleaned[0]["processes"][1]["parent_pid"], 1)
        self.assertEqual(cleaned[0]["events"][1]["wakeup_source"], 1)
        self.assertIsNone(cleaned[0]["events"][2]["wakeup_source"])
        self.assertEqual(cleaned[0]["outcomes"], [])
        self.assertNotIn("knightnm", json.dumps(cleaned))
        self.assertNotIn("/home", json.dumps(cleaned))
        validate_trace(cleaned[0])

    def test_cleaning_rejects_incomplete_traces_and_unsafe_sessions(self):
        from autoscheduler.real_clean import clean_traces

        trace = _trace()
        trace["metadata"]["truncated"] = True
        with self.assertRaisesRegex(ValueError, "incomplete"):
            clean_traces([trace], "pilot-clean")
        with self.assertRaisesRegex(ValueError, "safe identifier"):
            clean_traces([_trace()], "pilot/clean")

    def test_cleaning_rejects_events_outside_the_process_set(self):
        from autoscheduler.real_clean import clean_traces

        trace = _trace()
        trace["events"][0]["pid"] = 777
        with self.assertRaisesRegex(ValueError, "unknown process"):
            clean_traces([trace], "pilot-clean")

    def test_cli_writes_clean_canonical_trace(self):
        from autoscheduler.real_traces import read_traces, write_traces

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.jsonl", root / "clean.jsonl"
            write_traces([_trace()], source)
            completed = subprocess.run(
                [sys.executable, "main.py", "real-trace-clean", source,
                 "--capture-session", "pilot-clean", "--output", output],
                check=True, capture_output=True, text=True,
            )

            self.assertIn("Cleaned traces: 1", completed.stdout)
            self.assertEqual(read_traces(output)[0]["metadata"]["trace_id"], "pilot-clean-trace-0001")


if __name__ == "__main__":
    unittest.main()
