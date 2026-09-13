import unittest

from autoscheduler.experiments import evaluate_model
from autoscheduler.priority_rr import tune_priority_rr


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


if __name__ == "__main__":
    unittest.main()
