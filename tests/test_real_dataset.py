import copy
import unittest

from autoscheduler.fairness import FAIRNESS_FIELDS


def _event(timestamp_ms, pid, event_type, priority=120, previous_state=None):
    return {"timestamp_ns": timestamp_ms * 1_000_000, "cpu": 0, "pid": pid, "type": event_type,
            "priority": priority, "previous_state": previous_state, "ready_count": None, "wakeup_source": None}


def _trace():
    return {
        "schema_version": 1,
        "metadata": {"trace_id": "pilot-trace-1", "source": "linux", "application": "cpu",
                     "workload_family": "cpu", "scenario": "cpu-demo", "configuration_id": "cpu-demo",
                     "capture_session": "pilot", "affinity_cpu": 0, "anonymized": True, "truncated": False},
        "events": [
            _event(0, 1, "arrival"), _event(0, 2, "arrival"),
            _event(1, 1, "switch_in"), _event(8, 1, "switch_out", previous_state="Z"), _event(9, 1, "exit"),
            _event(10, 2, "switch_in"), _event(13, 2, "switch_out", previous_state="Z"), _event(14, 2, "exit"),
        ],
        "processes": [
            {"pid": 1, "arrival_ns": 0, "completion_ns": 9_000_000, "priority": 120, "parent_pid": None,
             "cgroup": None, "application_family": "cpu", "truncated": False},
            {"pid": 2, "arrival_ns": 0, "completion_ns": 14_000_000, "priority": 120, "parent_pid": None,
             "cgroup": None, "application_family": "cpu", "truncated": False},
        ], "outcomes": [],
    }


class RealDatasetTests(unittest.TestCase):
    def test_offline_replay_rows_link_observed_snapshots_to_every_deployable_action(self):
        from autoscheduler.real_config import load_real_config
        from autoscheduler.real_dataset import build_development_action_rows

        config = copy.deepcopy(load_real_config())
        config["control"].update({"initial_observation_ms": 2, "feature_window_ms": 2, "decision_interval_ms": 2})
        rows, summary = build_development_action_rows([_trace()], config)

        self.assertEqual(summary["label_provenance"], "pilot_offline_replay_development_only")
        self.assertEqual(summary["accepted_traces"], 1)
        self.assertEqual({row["action"] for row in rows}, {"FCFS", "Round Robin", "Priority", "Priority RR", "MLFQ"})
        self.assertTrue(all(row["source_result"].startswith("pilot-trace-1:") for row in rows))
        self.assertTrue(all(row["policy_cost"] >= 0 for row in rows))
        self.assertTrue(all(field in row for row in rows for field in FAIRNESS_FIELDS))

    def test_real_dataset_rejects_unanonymized_input(self):
        from autoscheduler.real_config import load_real_config
        from autoscheduler.real_dataset import build_development_action_rows

        trace = _trace()
        trace["metadata"]["anonymized"] = False
        with self.assertRaisesRegex(ValueError, "anonymized"):
            build_development_action_rows([trace], load_real_config())

    def test_synthetic_trace_rows_are_marked_development_only(self):
        from autoscheduler.real_config import load_real_config
        from autoscheduler.real_dataset import build_development_action_rows

        trace = _trace()
        trace["metadata"]["source"] = "synthetic"
        _, summary = build_development_action_rows([trace], load_real_config())

        self.assertEqual(summary["label_provenance"], "synthetic_development_only")


if __name__ == "__main__":
    unittest.main()
