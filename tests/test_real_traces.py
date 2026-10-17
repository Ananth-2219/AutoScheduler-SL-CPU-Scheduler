import copy
import tempfile
import unittest
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "real_traces" / "source_tiers.jsonl"


class RealTraceContractTests(unittest.TestCase):
    def test_source_tier_fixtures_validate_and_preserve_nulls(self):
        from autoscheduler.real_traces import read_traces

        traces = read_traces(FIXTURE)

        self.assertEqual([trace["metadata"]["source"] for trace in traces], ["synthetic", "azure", "linux"])
        self.assertIsNone(traces[1]["events"][0]["cpu"])
        self.assertIsNone(traces[1]["processes"][0]["priority"])

    def test_jsonl_round_trip_preserves_values_and_nulls(self):
        from autoscheduler.real_traces import read_traces, write_traces

        traces = read_traces(FIXTURE)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "traces.jsonl"
            write_traces(traces, output)
            self.assertEqual(read_traces(output), traces)

    def test_non_monotonic_events_are_rejected_with_trace_id(self):
        from autoscheduler.real_traces import read_traces, validate_trace

        trace = copy.deepcopy(read_traces(FIXTURE)[0])
        trace["events"][1]["timestamp_ns"] = -1

        with self.assertRaisesRegex(ValueError, "synthetic-1: event timestamps must be monotonic"):
            validate_trace(trace)

    def test_incomplete_process_requires_truncated_flag(self):
        from autoscheduler.real_traces import read_traces, validate_trace

        trace = copy.deepcopy(read_traces(FIXTURE)[0])
        trace["processes"][0]["completion_ns"] = None

        with self.assertRaisesRegex(ValueError, "synthetic-1: process 1 has no completion"):
            validate_trace(trace)

    def test_explicitly_truncated_process_may_lack_completion(self):
        from autoscheduler.real_traces import read_traces, validate_trace

        trace = copy.deepcopy(read_traces(FIXTURE)[0])
        trace["processes"][0]["completion_ns"] = None
        trace["processes"][0]["truncated"] = True

        validate_trace(trace)


if __name__ == "__main__":
    unittest.main()
