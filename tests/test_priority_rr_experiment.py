import unittest

from autoscheduler.experiments import evaluate_model
from autoscheduler.priority_rr import _validation_workloads, tune_priority_rr


class _FixedSjfModel:
    def predict(self, rows):
        return ["SJF" for _ in rows]


class PriorityRrExperimentTests(unittest.TestCase):
    def test_priority_rr_gate_requires_score_and_max_wait_improvement(self):
        _, summary = evaluate_model(_FixedSjfModel(), samples_per_profile=1, seed=99)
        priority_rr = summary["static_policies"]["Priority RR"]
        sjf = summary["static_policies"]["SJF"]
        self.assertEqual(
            summary["priority_rr_beats_sjf"],
            priority_rr["mean_score"] < sjf["mean_score"]
            and priority_rr["max_waiting_time"] < sjf["max_waiting_time"],
        )

    def test_priority_rr_tuning_returns_all_grid_candidates(self):
        report = tune_priority_rr(samples_per_profile=5, seed=42)
        self.assertEqual(len(report["candidates"]), 9)
        self.assertIn(report["selected"]["quantum"], {1, 2, 4})
        self.assertIn(report["selected"]["aging_interval"], {4, 8, 12})

    def test_tuning_workloads_are_profile_stratified_and_deterministic(self):
        first = _validation_workloads(samples_per_profile=5, seed=42)
        second = _validation_workloads(samples_per_profile=5, seed=42)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 5)
        self.assertEqual({workload.profile for workload in first}, {
            "interactive", "batch", "cpu_intensive", "io_intensive", "mixed"
        })
        self.assertEqual(len({workload.seed for workload in first}), len(first))


if __name__ == "__main__":
    unittest.main()
