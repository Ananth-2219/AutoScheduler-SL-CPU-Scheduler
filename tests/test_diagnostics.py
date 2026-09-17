import csv
import tempfile
import unittest
from pathlib import Path

from autoscheduler.experiments import evaluate_model, paired_bootstrap_ci, save_evaluation
from autoscheduler.fairness import FAIRNESS_FIELDS
from autoscheduler.features import FEATURE_NAMES


class _FixedSjfModel:
    def predict(self, rows):
        return ["SJF" for _ in rows]


class DiagnosticTests(unittest.TestCase):
    def test_evaluation_reports_diagnostics_and_constant_sjf(self):
        rows, summary = evaluate_model(
            _FixedSjfModel(), samples_per_profile=1, seed=55,
            frozen_static_baseline="Round Robin", bootstrap_samples=100,
        )

        matrix_total = sum(
            count
            for selections in summary["confusion_matrix"].values()
            for count in selections.values()
        )
        self.assertEqual(matrix_total, len(rows))
        self.assertEqual(
            sum(sum(counts.values()) for counts in summary["oracle_label_distribution"].values()),
            len(rows),
        )
        self.assertEqual(
            sum(sum(counts.values()) for counts in summary["selected_label_distribution"].values()),
            len(rows),
        )
        self.assertEqual(set(summary["feature_importance"]), set(FEATURE_NAMES))
        self.assertTrue(
            set(FAIRNESS_FIELDS).issubset(summary["static_policies"]["SJF"])
        )
        self.assertEqual(
            summary["constant_sjf"]["mean_score"],
            sum(row["score_sjf"] for row in rows) / len(rows),
        )
        self.assertEqual(
            summary["adaptive_beats_sjf"],
            summary["adaptive"]["mean_score"] < summary["constant_sjf"]["mean_score"],
        )
        self.assertEqual(summary["frozen_static_baseline"], "Round Robin")
        self.assertIn("ci_low", summary["paired_score_difference"])
        self.assertIn("paired_score_difference", summary["per_profile"]["mixed"])
        difference = summary["paired_score_difference"]
        self.assertEqual(
            summary["adaptive_statistically_beats_static"],
            difference["mean"] < 0 and difference["ci_high"] < 0,
        )

    def test_save_evaluation_writes_diagnostic_artifacts(self):
        rows, summary = evaluate_model(
            _FixedSjfModel(), samples_per_profile=1, seed=56, bootstrap_samples=100
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            save_evaluation(rows, summary, output)
            self.assertTrue((output / "confusion_matrix.csv").exists())
            self.assertTrue((output / "feature_importance.csv").exists())
            self.assertTrue((output / "diagnostics.png").exists())
            self.assertTrue((output / "fairness_metrics.csv").exists())
            self.assertTrue((output / "fairness.png").exists())
            with (output / "confusion_matrix.csv").open(newline="", encoding="utf-8") as file:
                self.assertEqual(sum(int(row["count"]) for row in csv.DictReader(file)), len(rows))

    def test_paired_bootstrap_is_deterministic_and_strict(self):
        first = paired_bootstrap_ci([-0.2, -0.1, -0.3], samples=200, seed=2027)
        second = paired_bootstrap_ci([-0.2, -0.1, -0.3], samples=200, seed=2027)
        self.assertEqual(first, second)
        self.assertLess(first["ci_high"], 0)
        zero = paired_bootstrap_ci([0.0, 0.0], samples=20, seed=2027)
        self.assertEqual(zero["ci_high"], 0.0)


if __name__ == "__main__":
    unittest.main()
