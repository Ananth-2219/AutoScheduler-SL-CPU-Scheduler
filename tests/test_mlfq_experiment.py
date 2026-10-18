import unittest

from autoscheduler.benefit import BenefitConfig, _complete, _observe, run_fixed_hybrid
from autoscheduler.evaluation import ALGORITHMS
from autoscheduler.mlfq_experiment import apply_decision_gates
from simulator.process import Process


class MlfqExperimentTests(unittest.TestCase):
    def test_mlfq_does_not_change_existing_six_policy_set(self):
        self.assertEqual(len(ALGORITHMS), 6)
        self.assertNotIn("MLFQ", ALGORITHMS)

    def test_fixed_hybrid_matches_rr_warmup_plus_srtf_continuation(self):
        processes = [Process("A", 0, 12), Process("B", 3, 2)]
        config = BenefitConfig(1, 20, 0.0)
        expected = _complete(_observe(processes, config), "SRTF", config)
        actual = run_fixed_hybrid(processes, 1, 20)
        self.assertEqual(actual.timeline, expected.timeline)
        self.assertEqual(actual.process_metrics, expected.process_metrics)

    def test_balanced_gates_require_strict_latency_and_fairness(self):
        evaluation = {
            "score_gate": True,
            "fairness_gate": True,
            "profile_wins": 1,
            "profile_losses": 4,
            "policies": {
                "Tuned RR": {"mean_score": 0.11},
                "SRTF": {"mean_score": 0.16},
                "RR20-SRTF": {"mean_score": 0.04},
                "MLFQ": {"mean_score": 0.03},
            },
        }
        latency = {name: {"passes_gate": True} for name in evaluation["policies"]}
        decision = apply_decision_gates(evaluation, latency)
        self.assertTrue(decision["mlfq_wins"])
        self.assertTrue(decision["recommend_ml_next"])
        self.assertEqual(decision["recommended_policy"], "MLFQ")

        latency["MLFQ"]["passes_gate"] = False
        decision = apply_decision_gates(evaluation, latency)
        self.assertFalse(decision["mlfq_wins"])
        self.assertFalse(decision["recommend_ml_next"])
        self.assertEqual(decision["recommended_policy"], "RR20-SRTF")

    def test_profile_variation_can_expose_ml_tuning_opportunity(self):
        evaluation = {
            "score_gate": False,
            "fairness_gate": True,
            "profile_wins": 2,
            "profile_losses": 3,
            "policies": {
                "Tuned RR": {"mean_score": 0.10},
                "SRTF": {"mean_score": 0.12},
                "RR20-SRTF": {"mean_score": 0.08},
                "MLFQ": {"mean_score": 0.09},
            },
        }
        latency = {name: {"passes_gate": True} for name in evaluation["policies"]}
        decision = apply_decision_gates(evaluation, latency)
        self.assertFalse(decision["mlfq_wins"])
        self.assertTrue(decision["profile_tuning_opportunity"])
        self.assertTrue(decision["recommend_ml_next"])


if __name__ == "__main__":
    unittest.main()
