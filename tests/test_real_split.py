import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _rows():
    rows = []
    for group in range(6):
        for decision in range(3):
            rows.append({
                "trace_id": f"trace-{group}",
                "application": f"app-{group % 2}",
                "workload_family": "cpu",
                "scenario": f"scenario-{group}",
                "configuration_id": f"config-{group}",
                "capture_session": "session-1",
                "decision_timestamp_ns": str(decision),
            })
    return rows


class RealTraceSplitTests(unittest.TestCase):
    def test_split_is_reproducible_and_never_leaks_a_group(self):
        from autoscheduler.real_split import split_feature_rows

        first = split_feature_rows(_rows(), {"train": 0.6, "validation": 0.2, "test": 0.2},
                                   ("application", "scenario", "capture_session"), 7001)
        second = split_feature_rows(_rows(), {"train": 0.6, "validation": 0.2, "test": 0.2},
                                    ("application", "scenario", "capture_session"), 7001)

        self.assertEqual(first, second)
        trace_sets = {
            name: {row["trace_id"] for row in rows}
            for name, rows in first.items()
        }
        self.assertTrue(all(trace_sets.values()))
        self.assertFalse(
            trace_sets["train"] & trace_sets["validation"]
            or trace_sets["train"] & trace_sets["test"]
            or trace_sets["validation"] & trace_sets["test"]
        )
        self.assertEqual(sum(map(len, first.values())), len(_rows()))

    def test_split_rejects_missing_group_fields_and_too_few_groups(self):
        from autoscheduler.real_split import split_feature_rows

        with self.assertRaisesRegex(ValueError, "scenario"):
            split_feature_rows([{"application": "a", "capture_session": "s"}],
                               {"train": 0.6, "validation": 0.2, "test": 0.2},
                               ("application", "scenario", "capture_session"), 7001)
        with self.assertRaisesRegex(ValueError, "three distinct"):
            split_feature_rows(_rows()[:2], {"train": 0.6, "validation": 0.2, "test": 0.2},
                               ("application", "scenario", "capture_session"), 7001)

    def test_cli_writes_a_grouped_split_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "features.csv", root / "split.json"
            with source.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=list(_rows()[0]))
                writer.writeheader()
                writer.writerows(_rows())

            completed = subprocess.run(
                [sys.executable, "main.py", "real-split", source, "--output", output],
                check=True, capture_output=True, text=True,
            )
            manifest = json.loads(output.read_text(encoding="utf-8"))

            self.assertIn("Train traces:", completed.stdout)
            self.assertEqual(manifest["group_by"], ["application", "scenario", "capture_session"])
            self.assertEqual(sum(manifest["row_counts"].values()), len(_rows()))


if __name__ == "__main__":
    unittest.main()
