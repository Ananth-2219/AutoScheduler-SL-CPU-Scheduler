import tempfile
import unittest
from pathlib import Path

from autoscheduler.adaptive import run_adaptive
from autoscheduler.dataset import build_dataset
from autoscheduler.evaluation import run_algorithm
from autoscheduler.evaluation import SELECTOR_ALGORITHMS
from autoscheduler.features import FEATURE_NAMES
from autoscheduler.workloads import generate_workload


class _FixedModel:
    def predict(self, rows):
        return ["FCFS" for _ in rows]


class LearningTests(unittest.TestCase):
    def test_candidate_selection_prefers_regret_over_accuracy(self):
        from autoscheduler.model import _candidate_key

        lower_accuracy_lower_regret = {
            "validation_accuracy": 0.50,
            "validation_mean_regret": 0.01,
            "min_samples_leaf": 10,
        }
        higher_accuracy_higher_regret = {
            "validation_accuracy": 0.90,
            "validation_mean_regret": 0.02,
            "min_samples_leaf": 1,
        }
        self.assertLess(
            _candidate_key(lower_accuracy_lower_regret, 1),
            _candidate_key(higher_accuracy_higher_regret, 0),
        )
        self.assertLess(
            _candidate_key({**lower_accuracy_lower_regret, "min_samples_leaf": 10}, 0),
            _candidate_key({**lower_accuracy_lower_regret, "min_samples_leaf": 1}, 0),
        )

    def test_dataset_has_unique_reproducible_seeds(self):
        first = build_dataset(samples_per_profile=2, seed=42)
        second = build_dataset(samples_per_profile=2, seed=42)
        self.assertEqual(first, second)
        self.assertEqual(len({row["seed"] for row in first}), len(first))
        self.assertTrue({row["label"] for row in first}.issubset(SELECTOR_ALGORITHMS))

    def test_adaptive_result_matches_selected_static_algorithm(self):
        workload = generate_workload("mixed", 91, 10)
        adaptive = run_adaptive(workload.processes, _FixedModel())
        direct = run_algorithm("FCFS", workload.processes)
        self.assertEqual(adaptive.selected_algorithm, "FCFS")
        self.assertEqual(adaptive.simulation, direct)
        self.assertEqual(tuple(adaptive.features), FEATURE_NAMES)
        self.assertGreaterEqual(adaptive.inference_ms, 0)

    def test_small_decision_tree_can_train_save_and_load(self):
        try:
            from autoscheduler.model import load_model, train_model
        except ModuleNotFoundError as error:
            self.skipTest(str(error))

        rows = build_dataset(samples_per_profile=20, seed=100)
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "model.joblib"
            report = train_model(rows, model_path, random_state=100)
            model = load_model(model_path)
            prediction = model.predict([[rows[0][name] for name in FEATURE_NAMES]])[0]
            self.assertTrue(model_path.exists())
            self.assertIn(prediction, {row["label"] for row in rows})
            self.assertGreaterEqual(report["test_accuracy"], 0)
            self.assertLessEqual(report["test_accuracy"], 1)
            self.assertGreaterEqual(report["validation_mean_regret"], 0)
            self.assertGreaterEqual(report["test_mean_regret"], 0)
            self.assertEqual(set(report["feature_importance"]), set(FEATURE_NAMES))


if __name__ == "__main__":
    unittest.main()
