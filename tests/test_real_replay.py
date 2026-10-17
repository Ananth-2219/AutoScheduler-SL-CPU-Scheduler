import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def event(timestamp_ms, pid, event_type, cpu=0, priority=120, previous_state=None):
    return {
        "timestamp_ns": timestamp_ms * 1_000_000,
        "cpu": cpu,
        "pid": pid,
        "type": event_type,
        "priority": priority,
        "previous_state": previous_state,
        "ready_count": None,
        "wakeup_source": None,
    }


def trace(events, processes, truncated=False):
    return {
        "schema_version": 1,
        "metadata": {
            "trace_id": "replay-fixture",
            "source": "linux",
            "affinity_cpu": 0,
            "truncated": truncated,
        },
        "events": events,
        "processes": processes,
        "outcomes": [],
    }


def process(pid, completion=20, priority=120, truncated=False):
    return {
        "pid": pid,
        "arrival_ns": 0,
        "completion_ns": completion * 1_000_000 if completion is not None else None,
        "priority": priority,
        "parent_pid": None,
        "cgroup": None,
        "application_family": "fixture",
        "truncated": truncated,
    }


class RealReplayTests(unittest.TestCase):
    def test_converter_accumulates_preemptions_and_rebuilds_cpu_io_bursts(self):
        from autoscheduler.real_replay import build_replay_workload

        source = trace(
            [
                event(0, 1, "arrival"),
                event(1, 1, "switch_in"),
                event(4, 1, "switch_out", previous_state="R"),
                event(6, 1, "switch_in"),
                event(8, 1, "switch_out", previous_state="S"),
                event(10, 1, "wakeup"),
                event(11, 1, "switch_in"),
                event(15, 1, "switch_out", previous_state="Z"),
                event(16, 1, "exit"),
            ],
            [process(1, completion=16)],
        )

        replay = build_replay_workload(source)

        self.assertEqual(replay.rejected_processes, {})
        rebuilt = replay.processes[0]
        self.assertEqual(rebuilt.arrival_time, 0)
        self.assertEqual(rebuilt.cpu_bursts, (5, 4))
        self.assertEqual(rebuilt.io_bursts, (2,))
        self.assertEqual(rebuilt.priority, 20)

    def test_converter_rejects_migrated_process_but_keeps_valid_processes(self):
        from autoscheduler.real_replay import build_replay_workload

        source = trace(
            [
                event(0, 1, "arrival"), event(1, 1, "switch_in"),
                event(4, 1, "switch_out", previous_state="Z"), event(5, 1, "exit"),
                event(0, 2, "arrival"), event(1, 2, "switch_in", cpu=1),
                event(4, 2, "switch_out", cpu=1, previous_state="Z"), event(5, 2, "exit", cpu=1),
            ],
            [process(1, completion=5), process(2, completion=5)],
        )

        replay = build_replay_workload(source)

        self.assertEqual([item.pid for item in replay.processes], ["replay-fixture:1"])
        self.assertEqual(replay.rejected_processes, {2: "migrated_cpu"})

    def test_converter_handles_switch_in_just_before_recorded_arrival(self):
        from autoscheduler.real_replay import build_replay_workload

        late_process = process(1, completion=16)
        late_process["arrival_ns"] = 10_000_000
        source = trace(
            [
                event(9, 1, "switch_in"),
                event(15, 1, "switch_out", previous_state="Z"),
                event(16, 1, "exit"),
            ],
            [late_process],
        )

        replay = build_replay_workload(source)

        self.assertEqual(replay.processes[0].arrival_time, 1)
        self.assertEqual(replay.processes[0].cpu_bursts, (5,))

    def test_converter_ignores_terminal_switch_out_after_exit(self):
        from autoscheduler.real_replay import build_replay_workload

        source = trace(
            [
                event(0, 1, "arrival"),
                event(1, 1, "switch_in"),
                event(5, 1, "exit"),
                event(5, 1, "switch_out", previous_state="Z"),
            ],
            [process(1, completion=5)],
        )

        replay = build_replay_workload(source)

        self.assertEqual(replay.processes[0].cpu_bursts, (4,))

    def test_converter_rejects_truncated_trace(self):
        from autoscheduler.real_replay import build_replay_workload

        source = trace([event(0, 1, "arrival")], [process(1, completion=None, truncated=True)], truncated=True)

        with self.assertRaisesRegex(ValueError, "truncated"):
            build_replay_workload(source)

    def test_manifest_preserves_reconstructed_processes_and_rejections(self):
        from autoscheduler.real_replay import build_replay_manifest

        source = trace(
            [
                event(0, 1, "arrival"), event(1, 1, "switch_in"),
                event(2, 1, "switch_out", previous_state="Z"), event(3, 1, "exit"),
                event(0, 2, "arrival"), event(1, 2, "switch_in", cpu=1),
                event(2, 2, "switch_out", cpu=1, previous_state="Z"), event(3, 2, "exit", cpu=1),
            ],
            [process(1, completion=3), process(2, completion=3)],
        )

        manifest = build_replay_manifest([source])

        self.assertEqual(manifest["summary"], {
            "accepted_traces": 1, "rejected_traces": 0,
            "accepted_processes": 1, "rejected_processes": 1,
        })
        entry = manifest["traces"][0]
        self.assertEqual(entry["status"], "accepted")
        self.assertEqual(entry["rejected_processes"], [{"pid": 2, "reason": "migrated_cpu"}])
        self.assertEqual(entry["processes"][0]["cpu_bursts"], [1])

    def test_manifest_explicitly_rejects_a_trace_with_no_eligible_processes(self):
        from autoscheduler.real_replay import build_replay_manifest

        source = trace(
            [event(0, 1, "arrival")],
            [process(1, completion=None, truncated=True)],
            truncated=True,
        )

        manifest = build_replay_manifest([source])

        self.assertEqual(manifest["summary"]["rejected_traces"], 1)
        self.assertEqual(manifest["traces"][0]["status"], "rejected")
        self.assertIn("truncated", manifest["traces"][0]["reason"])

    def test_cli_writes_replay_manifest(self):
        from autoscheduler.real_traces import write_traces

        source = trace(
            [
                event(0, 1, "arrival"), event(1, 1, "switch_in"),
                event(2, 1, "switch_out", previous_state="Z"), event(3, 1, "exit"),
            ],
            [process(1, completion=3)],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "trace.jsonl"
            output_path = root / "replay.json"
            write_traces([source], input_path)

            result = subprocess.run(
                [sys.executable, "main.py", "real-replay-build", input_path, "--output", output_path],
                check=True, capture_output=True, text=True,
            )

            self.assertIn("Accepted processes: 1", result.stdout)
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["summary"]["accepted_processes"], 1)


if __name__ == "__main__":
    unittest.main()
