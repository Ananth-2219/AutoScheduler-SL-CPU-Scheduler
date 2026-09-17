import unittest

from autoscheduler.latency import percentile, select_recommended_policy


class LatencyTests(unittest.TestCase):
    def test_percentile_and_strict_gate_selection(self):
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.50), 2.5)
        summary = {
            "SJF": {"small": {"p99_ms": 9.9}, "medium": {"p99_ms": 9.9}, "large": {"p99_ms": 9.9}},
            "Round Robin": {"small": {"p99_ms": 10.0}, "medium": {"p99_ms": 1.0}, "large": {"p99_ms": 1.0}},
            "Adaptive": {"small": {"p99_ms": 1.0}, "medium": {"p99_ms": 1.0}, "large": {"p99_ms": 1.0}},
        }
        choice = select_recommended_policy(
            summary, {"SJF": 0.2, "Round Robin": 0.1, "Adaptive": 0.3}
        )
        self.assertEqual(choice["best_static_policy"], "SJF")
        self.assertEqual(choice["recommended_policy"], "SJF")
        self.assertFalse(choice["adaptive_beats_static"])

        statistically_blocked = select_recommended_policy(
            summary,
            {"SJF": 0.2, "Round Robin": 0.1, "Adaptive": 0.01},
            adaptive_statistically_beats_static=False,
        )
        self.assertEqual(statistically_blocked["recommended_policy"], "SJF")
        self.assertFalse(statistically_blocked["eligible_for_adaptive"])


if __name__ == "__main__":
    unittest.main()
