import unittest

from scheduler.mlfq import mlfq
from simulator.process import Process
from simulator.simulator import run_simulation


class MlfqTests(unittest.TestCase):
    def test_full_quantum_demotes_and_keeps_fifo_order(self):
        _, timeline = mlfq([Process("A", 0, 6), Process("B", 0, 1)])
        self.assertEqual(timeline, [("A", 0, 2), ("B", 2, 3), ("A", 3, 7)])

    def test_io_return_enters_top_queue_and_preempts_lower_queue(self):
        _, timeline = mlfq([
            Process("A", 0, 2, cpu_bursts=(1, 1), io_bursts=(2,)),
            Process("B", 0, 8),
        ])
        self.assertEqual(timeline[:3], [("A", 0, 1), ("B", 1, 3), ("A", 3, 4)])

    def test_higher_queue_arrival_preempts_and_preserves_unused_quantum(self):
        _, timeline = mlfq([Process("A", 0, 10), Process("B", 3, 1)])
        self.assertEqual(timeline[:5], [
            ("A", 0, 2), ("A", 2, 3), ("B", 3, 4), ("A", 4, 7), ("A", 7, 11),
        ])

    def test_equal_queue_arrival_does_not_preempt(self):
        _, timeline = mlfq([Process("A", 0, 4), Process("B", 1, 1)])
        self.assertEqual(timeline[0], ("A", 0, 2))

    def test_aging_promotes_after_20_waiting_ticks_not_19(self):
        processes = [Process("A", 0, 3)]
        processes.extend(Process(f"P{time}", time, 1) for time in range(1, 22))
        processes.append(Process("P23", 23, 1))
        _, timeline = mlfq(processes)
        starts = [(pid, start) for pid, start, _ in timeline]
        self.assertLess(starts.index(("P20", 21)), starts.index(("A", 23)))
        self.assertLess(starts.index(("P21", 22)), starts.index(("A", 23)))
        self.assertLess(starts.index(("A", 23)), starts.index(("P23", 24)))

    def test_every_cpu_io_process_completes_once(self):
        processes = [
            Process("A", 0, 5, cpu_bursts=(2, 3), io_bursts=(4,)),
            Process("B", 1, 4, cpu_bursts=(1, 2, 1), io_bursts=(2, 3)),
            Process("C", 2, 6),
        ]
        result = run_simulation("MLFQ", mlfq, processes)
        self.assertEqual({metric.pid for metric in result.process_metrics}, {"A", "B", "C"})
        self.assertEqual(len(result.process_metrics), 3)
        self.assertTrue(all(metric.waiting_time >= 0 for metric in result.process_metrics))

    def test_invalid_quanta_and_aging_are_rejected(self):
        processes = [Process("A", 0, 1)]
        with self.assertRaises(ValueError):
            mlfq(processes, quanta=(2, 0, 8))
        with self.assertRaises(ValueError):
            mlfq(processes, aging_threshold=0)


if __name__ == "__main__":
    unittest.main()
