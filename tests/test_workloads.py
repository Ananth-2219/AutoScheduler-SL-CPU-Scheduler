import unittest

from autoscheduler.evaluation import ALGORITHMS, compare_algorithms, oracle_label
from autoscheduler.features import FEATURE_NAMES, extract_features
from autoscheduler.workloads import PROFILES, generate_workload


class WorkloadTests(unittest.TestCase):
    def test_generation_is_reproducible_for_every_profile(self):
        for profile in PROFILES:
            first = generate_workload(profile, seed=42, process_count=8)
            second = generate_workload(profile, seed=42, process_count=8)
            self.assertEqual(first, second)

    def test_io_profile_contains_multiple_cpu_bursts(self):
        workload = generate_workload("io_intensive", seed=7, process_count=8)
        self.assertTrue(all(len(process.cpu_bursts) >= 3 for process in workload.processes))
        self.assertTrue(all(process.io_bursts for process in workload.processes))

    def test_features_have_fixed_order_and_no_result_metrics(self):
        features = extract_features(generate_workload("mixed", 12, 10).processes)
        self.assertEqual(tuple(features), FEATURE_NAMES)
        self.assertNotIn("waiting_time", features)
        self.assertNotIn("turnaround_time", features)

    def test_every_algorithm_completes_each_process_once(self):
        workload = generate_workload("mixed", seed=9, process_count=12)
        results = compare_algorithms(workload.processes)
        self.assertEqual(set(results), set(ALGORITHMS))
        for result in results.values():
            completed = [metric.pid for metric in result.process_metrics]
            self.assertEqual(len(completed), len(set(completed)))
            self.assertEqual(set(completed), {process.pid for process in workload.processes})
            self.assertGreaterEqual(result.cpu_utilization, 0)
            self.assertLessEqual(result.cpu_utilization, 1)

    def test_priority_round_robin_is_a_static_baseline(self):
        results = compare_algorithms(generate_workload("mixed", seed=9, process_count=12).processes)
        result = results["Priority RR"]
        self.assertGreater(result.context_switch_time, 0)
        self.assertGreaterEqual(result.max_waiting_time, result.avg_waiting_time)

    def test_oracle_returns_one_algorithm_and_normalized_scores(self):
        results = compare_algorithms(generate_workload("batch", 2, 10).processes)
        label, scores = oracle_label(results)
        self.assertIn(label, ALGORITHMS)
        self.assertEqual(set(scores), set(ALGORITHMS))
        self.assertTrue(all(0 <= score <= 1 for score in scores.values()))
        self.assertEqual(scores[label], min(scores.values()))

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_workload("unknown", 1)


if __name__ == "__main__":
    unittest.main()
