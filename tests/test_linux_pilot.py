import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
PILOT = ROOT / "tools" / "capture_linux_pilot.sh"
FULL = ROOT / "tools" / "capture_linux_full.sh"
WAKEUP = ROOT / "tools" / "run_wakeup_probe.py"


class LinuxPilotTests(unittest.TestCase):
    def test_wakeup_probe_runs_and_rejects_non_positive_duration(self):
        completed = subprocess.run(
            [sys.executable, WAKEUP, "0.02"],
            check=True,
            capture_output=True,
            text=True,
        )
        rejected = subprocess.run(
            [sys.executable, WAKEUP, "0"],
            capture_output=True,
            text=True,
        )

        self.assertIn("wakeup cycles=", completed.stdout)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("duration must be positive", rejected.stderr)

    def test_wakeup_probe_accepts_configured_sleep_interval(self):
        completed = subprocess.run(
            [sys.executable, WAKEUP, "0.02", "--sleep-ms", "1"],
            check=True,
            capture_output=True,
            text=True,
        )
        rejected = subprocess.run(
            [sys.executable, WAKEUP, "0.02", "--sleep-ms", "0"],
            capture_output=True,
            text=True,
        )

        self.assertIn("wakeup cycles=", completed.stdout)
        self.assertNotEqual(rejected.returncode, 0)

    def test_full_dry_run_lists_thirty_configurations_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "full"
            completed = subprocess.run(
                ["bash", FULL, "--dry-run", output, "60", "1"],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.stdout.count("trace-cmd record"), 30)
            self.assertEqual(completed.stdout.count("configuration="), 30)
            self.assertIn("firefox-tabs-5", completed.stdout)
            self.assertNotIn("-M 1", completed.stdout)
            self.assertFalse(output.exists())

    def test_dry_run_lists_each_workload_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pilot"
            completed = subprocess.run(
                ["bash", PILOT, "--dry-run", output, "5"],
                check=True,
                capture_output=True,
                text=True,
            )

            for family in ("wakeup", "cpu", "io", "firefox", "compression", "mixed"):
                self.assertIn(family, completed.stdout)
            self.assertEqual(completed.stdout.count("trace-cmd record"), 6)
            self.assertNotIn("-M 1", completed.stdout)
            self.assertFalse(output.exists())

    def test_invalid_duration_is_rejected(self):
        completed = subprocess.run(
            ["bash", PILOT, "--dry-run", "/tmp/unused", "zero"],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("duration must be a positive integer", completed.stderr)


if __name__ == "__main__":
    unittest.main()
