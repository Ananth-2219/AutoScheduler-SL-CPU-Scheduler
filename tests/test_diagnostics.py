import csv
import tempfile
import unittest
from pathlib import Path

from autoscheduler.experiments import evaluate_model, save_evaluation
from autoscheduler.features import FEATURE_NAMES


class _FixedSjfModel:
    def predict(self, rows):
        return ["SJF" for _ in rows]


class DiagnosticTests(unittest.TestCase):
    def test_evaluation_reports_diagnostics_and_constant_sjf(self):
        rows, summary = evaluate_model(_FixedSjfModel(), samples_per_profile=1, seed=55)

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
        self.assertEqual(
            summary["constant_sjf"]["mean_score"],
            sum(row["score_sjf"] for row in rows) / len(rows),
        )
        self.assertEqual(
            summary["adaptive_beats_sjf"],
            summary["adaptive"]["mean_score"] < summary["constant_sjf"]["mean_score"],
        )
        self.assertEqual(
            summary["eligible_for_next_adaptive_phase"], summary["adaptive_beats_sjf"]
        )

    def test_save_evaluation_writes_diagnostic_artifacts(self):
        rows, summary = evaluate_model(_FixedSjfModel(), samples_per_profile=1, seed=56)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            save_evaluation(rows, summary, output)
            self.assertTrue((output / "confusion_matrix.csv").exists())
            self.assertTrue((output / "feature_importance.csv").exists())
            self.assertTrue((output / "diagnostics.png").exists())
            with (output / "confusion_matrix.csv").open(newline="", encoding="utf-8") as file:
                self.assertEqual(sum(int(row["count"]) for row in csv.DictReader(file)), len(rows))


if __name__ == "__main__":
    unittest.main()
