import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "main.py", *map(str, arguments)],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_train_compare_and_evaluate_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model.joblib"
            dataset = root / "training.csv"
            results = root / "results"

            trained = self.run_cli(
                "train",
                "--samples-per-profile",
                5,
                "--model",
                model,
                "--dataset",
                dataset,
            )
            self.assertIn("Test accuracy", trained.stdout)
            self.assertIn("Validation regret", trained.stdout)
            self.assertTrue(model.exists())
            self.assertTrue(dataset.exists())

            compared = self.run_cli(
                "compare", "--profile", "mixed", "--seed", 77, "--model", model
            )
            self.assertIn("Adaptive selected", compared.stdout)
            self.assertIn("CPU utilization", compared.stdout)

            evaluated = self.run_cli(
                "evaluate",
                "--samples-per-profile",
                1,
                "--model",
                model,
                "--output",
                results,
            )
            self.assertIn("Best static", evaluated.stdout)
            self.assertIn("Adaptive beats SJF", evaluated.stdout)
            self.assertTrue((results / "evaluation.csv").exists())
            self.assertTrue((results / "summary.json").exists())
            self.assertTrue((results / "scores.png").exists())
            self.assertTrue((results / "confusion_matrix.csv").exists())
            self.assertTrue((results / "feature_importance.csv").exists())
            self.assertTrue((results / "diagnostics.png").exists())


if __name__ == "__main__":
    unittest.main()
