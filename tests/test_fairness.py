import unittest

from autoscheduler.evaluation import run_algorithm
from autoscheduler.fairness import aggregate_fairness
from simulator.process import Process
from simulator.simulator import ProcessMetrics, run_simulation
from scheduler.fcfs import fcfs


def metric(pid, burst, waiting, priority, io=()):
    return ProcessMetrics(
        pid=pid,
        arrival_time=0,
        burst_time=burst,
        priority=priority,
        start_time=0,
        completion_time=burst + waiting,
        turnaround_time=burst + waiting,
        waiting_time=waiting,
        response_time=0,
        post_io_response_times=io,
    )


class FairnessTests(unittest.TestCase):
    def test_aggregates_pooled_waits_and_uses_strict_starvation_threshold(self):
        report = aggregate_fairness(
            [metric("P1", 2, 6, 1, (2,)), metric("P2", 2, 7, 2, (4,)), metric("P3", 1, 0, 4)]
        )
        self.assertEqual(report["max_waiting_time"], 7)
        self.assertEqual(report["p95_waiting_time"], 6.9)
        self.assertEqual(report["starvation_count"], 1)
        self.assertEqual(report["priority_mean_waiting_time"], 6.5)
        self.assertEqual(report["priority_max_waiting_time"], 7)
        self.assertEqual(report["post_io_mean_response_time"], 3)
        self.assertEqual(report["post_io_max_response_time"], 4)

    def test_empty_priority_and_io_groups_are_null(self):
        report = aggregate_fairness([metric("P1", 2, 1, 3)])
        self.assertIsNone(report["priority_mean_waiting_time"])
        self.assertIsNone(report["priority_max_waiting_time"])
        self.assertIsNone(report["post_io_mean_response_time"])
        self.assertIsNone(report["post_io_max_response_time"])

    def test_post_io_response_is_measured_from_io_completion(self):
        result = run_simulation(
            "FCFS",
            fcfs,
            [Process("P1", 0, 4, priority=1, cpu_bursts=(2, 2), io_bursts=(3,)), Process("P2", 1, 3)],
        )
        p1 = next(item for item in result.process_metrics if item.pid == "P1")
        self.assertEqual(p1.post_io_response_times, (0,))

    def test_deterministic_fairness_fixtures_complete_for_all_target_policies(self):
        fixtures = [
            [Process("long", 1, 12, priority=5), *[Process(f"short{i}", i, 1, priority=1) for i in range(1, 8)]],
            [Process("io", 0, 2, priority=2, cpu_bursts=(1, 1), io_bursts=(2,)), Process("cpu", 0, 8, priority=3)],
            [Process("low", 0, 8, priority=5), Process("high", 1, 1, priority=1)],
            [Process(f"P{i}", 0, 2, priority=1) for i in range(4)],
        ]
        for processes in fixtures:
            for name in ("SJF", "Round Robin", "Priority RR"):
                result = run_algorithm(name, processes)
                report = aggregate_fairness(result.process_metrics)
                self.assertEqual(len(result.process_metrics), len(processes))
                self.assertGreaterEqual(report["max_waiting_time"], 0)
                self.assertGreaterEqual(report["starvation_count"], 0)


if __name__ == "__main__":
    unittest.main()
