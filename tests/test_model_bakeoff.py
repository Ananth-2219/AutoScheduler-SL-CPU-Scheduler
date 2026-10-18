import unittest

from autoscheduler.real_features import FEATURE_NAMES


def _rows(start: int, count: int):
    rows = []
    for index in range(start, start + count):
        features = {name: float((index * (position + 3)) % 11) for position, name in enumerate(FEATURE_NAMES)}
        rows.append({**features, "policy_cost": 0.4 * features[FEATURE_NAMES[0]] + 0.1 * features[FEATURE_NAMES[1]]})
    return rows


def _mean_absolute_error(rows, predictions):
    return sum(abs(row["policy_cost"] - prediction) for row, prediction in zip(rows, predictions)) / len(rows)


class ModelBakeoffTests(unittest.TestCase):
    def test_simpler_family_wins_when_scores_are_within_the_frozen_tie_margin(self):
        from autoscheduler.model_bakeoff import _is_preferred

        simplicity = ("Dummy", "Ridge", "Decision Tree")
        simple = {"family": "Ridge", "validation_score": 1.0}
        complex_candidate = {"family": "Decision Tree", "validation_score": 0.998}

        self.assertFalse(_is_preferred(complex_candidate, simple, simplicity))
        self.assertTrue(_is_preferred(simple, complex_candidate, simplicity))

    def test_registry_covers_every_configured_family_with_a_capped_candidate_budget(self):
        from autoscheduler.model_bakeoff import candidate_configurations
        from autoscheduler.real_config import load_real_config

        config = load_real_config()
        candidates = candidate_configurations(config["models"])

        self.assertEqual(tuple(candidates), tuple(config["models"]["simplicity_order"]))
        self.assertTrue(all(1 <= len(settings) <= 12 for settings in candidates.values()))
        self.assertEqual(candidates["Dummy"], [{"strategy": "mean"}])

    def test_bakeoff_is_reproducible_and_uses_validation_score_not_hidden_test_rows(self):
        from autoscheduler.model_bakeoff import run_bakeoff
        from autoscheduler.real_config import load_real_config

        config = load_real_config()
        train, validation, test = _rows(0, 60), _rows(60, 30), _rows(90, 30)
        first = run_bakeoff(train, validation, test, FEATURE_NAMES, "policy_cost", config["models"], 7002,
                            _mean_absolute_error)
        second = run_bakeoff(train, validation, test, FEATURE_NAMES, "policy_cost", config["models"], 7002,
                             _mean_absolute_error)
        altered_test = [{**row, "policy_cost": row["policy_cost"] + 100.0} for row in test]
        sealed = run_bakeoff(train, validation, altered_test, FEATURE_NAMES, "policy_cost", config["models"], 7002,
                             _mean_absolute_error)

        self.assertEqual(first, second)
        self.assertEqual(set(first["families"]), set(config["models"]["families"]))
        self.assertEqual(first["selection_basis"], "caller_supplied_validation_scheduler_score")
        self.assertGreaterEqual(first["selected"]["test_score"], 0)
        self.assertEqual(len(first["families"]["Dummy"]), 1)
        self.assertEqual(first["selected"]["family"], sealed["selected"]["family"])
        self.assertEqual(first["selected"]["settings"], sealed["selected"]["settings"])
        self.assertNotEqual(first["selected"]["test_score"], sealed["selected"]["test_score"])

    def test_bakeoff_rejects_rows_without_policy_cost_labels(self):
        from autoscheduler.model_bakeoff import run_bakeoff
        from autoscheduler.real_config import load_real_config

        config = load_real_config()
        rows = [{name: 0.0 for name in FEATURE_NAMES} for _ in range(3)]
        with self.assertRaisesRegex(ValueError, "policy_cost"):
            run_bakeoff(rows, rows, rows, FEATURE_NAMES, "policy_cost", config["models"], 7002,
                        _mean_absolute_error)


if __name__ == "__main__":
    unittest.main()
