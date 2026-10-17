import copy
import subprocess
import sys
import unittest


class RealExperimentConfigTests(unittest.TestCase):
    def test_default_contract_is_valid_and_freezes_research_boundaries(self):
        from autoscheduler.real_config import DEFAULT_REAL_CONFIG, load_real_config

        config = load_real_config(DEFAULT_REAL_CONFIG)

        self.assertEqual(config["target"]["domain"], "single_cpu_desktop_interactive_linux")
        self.assertEqual(
            [policy["name"] for policy in config["policies"]["deployable"]],
            ["FCFS", "Round Robin", "Priority", "Priority RR", "MLFQ"],
        )
        self.assertEqual(
            [policy["name"] for policy in config["policies"]["oracle_only"]],
            ["SJF", "SRTF", "RR20-SRTF"],
        )
        self.assertEqual(config["data"]["synthetic_role"], "tests_stress_and_optional_pretraining_only")
        self.assertEqual(config["control"]["initial_observation_ms"], 2_000)
        self.assertEqual(config["control"]["decision_interval_ms"], 500)
        self.assertEqual(config["control"]["minimum_dwell_ms"], 2_000)
        self.assertAlmostEqual(sum(config["score_weights"].values()), 1.0)

    def test_hash_is_canonical_and_summary_stamp_does_not_mutate_input(self):
        from autoscheduler.real_config import DEFAULT_REAL_CONFIG, config_hash, load_real_config, stamp_summary

        first = {"b": [2, 1], "a": {"value": 3}}
        second = {"a": {"value": 3}, "b": [2, 1]}
        summary = {"samples": 12}
        config = load_real_config(DEFAULT_REAL_CONFIG)

        self.assertEqual(config_hash(first), config_hash(second))
        stamped = stamp_summary(summary, config, "fixture.json")
        self.assertEqual(summary, {"samples": 12})
        self.assertEqual(stamped["experiment_config"]["sha256"], config_hash(config))
        self.assertEqual(stamped["experiment_config"]["file"], "fixture.json")

    def test_validation_rejects_oracle_policy_as_deployable(self):
        from autoscheduler.real_config import DEFAULT_REAL_CONFIG, load_real_config, validate_real_config

        config = copy.deepcopy(load_real_config(DEFAULT_REAL_CONFIG))
        config["policies"]["deployable"].append({"name": "SRTF"})

        with self.assertRaisesRegex(ValueError, "deployable and oracle-only"):
            validate_real_config(config)

    def test_cli_prints_validated_contract_hash(self):
        completed = subprocess.run(
            [sys.executable, "main.py", "real-config"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Contract valid", completed.stdout)
        self.assertIn("SHA256:", completed.stdout)
        self.assertIn("Deployable policies: FCFS, Round Robin, Priority, Priority RR, MLFQ", completed.stdout)

    def test_invalid_split_is_rejected(self):
        from autoscheduler.real_config import DEFAULT_REAL_CONFIG, load_real_config, validate_real_config

        config = copy.deepcopy(load_real_config(DEFAULT_REAL_CONFIG))
        config["dataset"]["split"] = {"train": 0.7, "validation": 0.2, "test": 0.2}

        with self.assertRaisesRegex(ValueError, "split fractions"):
            validate_real_config(config)


if __name__ == "__main__":
    unittest.main()
