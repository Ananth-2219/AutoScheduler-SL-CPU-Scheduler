import unittest


class SyntheticTraceTests(unittest.TestCase):
    def test_synthetic_traces_are_deterministic_valid_and_replayable(self):
        from autoscheduler.real_replay import build_replay_workload
        from autoscheduler.real_synthetic import build_synthetic_traces
        from autoscheduler.real_traces import validate_trace

        traces = build_synthetic_traces(repetitions=1, seed=9001)

        self.assertEqual(traces, build_synthetic_traces(repetitions=1, seed=9001))
        self.assertEqual(len(traces), 5)
        for trace in traces:
            validate_trace(trace)
            self.assertEqual(trace["metadata"]["source"], "synthetic")
            self.assertIsInstance(trace["metadata"]["generation_seed"], int)
            self.assertGreaterEqual(len(build_replay_workload(trace).processes), 1)


if __name__ == "__main__":
    unittest.main()
