import tempfile
import unittest
from pathlib import Path

from autoscheduler.evaluation import compare_algorithms, run_algorithm, score_result_against_reference
from autoscheduler.benefit import (
    BENEFIT_FEATURE_NAMES,
    BenefitConfig,
    _complete,
    _observe,
    _split_workloads,
    _workloads,
    extract_observed_features,
    run_benefit,
)
from simulator.process import Process


class _DeltaModel:
    def __init__(self, delta):
        self.delta = delta
        self.calls = 0

    def predict(self, rows):
        self.calls += len(rows)
        return [self.delta for _ in rows]


class BenefitTests(unittest.TestCase):
    def test_fixed_reference_score_does_not_move_when_candidate_is_added(self):
        processes = [Process("A", 0, 8), Process("B", 1, 2)]
        reference = compare_algorithms(processes)
        rr = run_algorithm("Round Robin", processes)
        before = score_result_against_reference(rr, reference)
        reference_with_candidate = {**reference, "Adaptive": run_algorithm("SRTF", processes)}
        self.assertEqual(before, score_result_against_reference(rr, reference_with_candidate, reference_names=reference))

    def test_observed_features_ignore_hidden_future_bursts(self):
        config = BenefitConfig(rr_quantum=2, observation_ticks=0, margin=0.0)
        short = _observe([Process("A", 0, 2), Process("B", 0, 3)], config)
        long = _observe([Process("A", 0, 20), Process("B", 0, 30)], config)
        self.assertEqual(extract_observed_features(short), extract_observed_features(long))
        self.assertEqual(tuple(extract_observed_features(short)), BENEFIT_FEATURE_NAMES)

    def test_threshold_falls_back_to_rr_and_switches_only_for_clear_gain(self):
        processes = [Process("A", 0, 9), Process("B", 1, 2)]
        keep = run_benefit(processes, _DeltaModel(-0.004), BenefitConfig(2, 1, 0.005))
        equal = run_benefit(processes, _DeltaModel(-0.005), BenefitConfig(2, 1, 0.005))
        switch = run_benefit(processes, _DeltaModel(-0.006), BenefitConfig(2, 1, 0.005))
        self.assertEqual(keep.selected_policy, "Round Robin")
        self.assertEqual(equal.selected_policy, "Round Robin")
        self.assertEqual(switch.selected_policy, "SRTF")

    def test_selected_result_is_rr_warmup_plus_selected_continuation(self):
        processes = [Process("A", 0, 9), Process("B", 1, 2)]
        config = BenefitConfig(2, 1, 0.005)
        state = _observe(processes, config)
        result = run_benefit(processes, _DeltaModel(-0.006), config)
        expected = _complete(state, "SRTF", config)
        self.assertEqual(result.simulation.timeline, expected.timeline)
        self.assertEqual(result.simulation.process_metrics, expected.process_metrics)

    def test_trace_split_is_disjoint_and_reproducible(self):
        workloads = _workloads(5, 42)
        first = _split_workloads(workloads, 42)
        second = _split_workloads(workloads, 42)
        self.assertEqual(first, second)
        seed_sets = {
            name: {workloads[index].seed for index in indexes}
            for name, indexes in first.items()
        }
        self.assertFalse(seed_sets["train"] & seed_sets["validation"])
        self.assertFalse(seed_sets["train"] & seed_sets["test"])
        self.assertFalse(seed_sets["validation"] & seed_sets["test"])

    def test_completed_before_observation_uses_rr_without_inference(self):
        model = _DeltaModel(-1.0)
        result = run_benefit([Process("A", 0, 1)], model, BenefitConfig(2, 5, 0.0))
        self.assertEqual(result.selected_policy, "Round Robin")
        self.assertEqual(result.inference_ms, 0.0)
        self.assertEqual(model.calls, 0)
        self.assertEqual(result.simulation.timeline, [("A", 0, 1)])


if __name__ == "__main__":
    unittest.main()
