import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "tools" / "capture_linux_trace.sh"


class LinuxCollectorTests(unittest.TestCase):
    def test_version_probe_does_not_require_zero_exit_status(self):
        self.assertNotIn("text=True, check=True", SCRIPT.read_text(encoding="utf-8"))

    def test_dry_run_prints_scoped_trace_command_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "capture"
            completed = subprocess.run(
                ["bash", SCRIPT, "--dry-run", output, "0", "--", "sleep", "1"],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("trace-cmd record", completed.stdout)
            self.assertIn("sched:sched_wakeup", completed.stdout)
            self.assertIn("sched:sched_switch", completed.stdout)
            self.assertIn("-M 1", completed.stdout)
            self.assertIn("--user", completed.stdout)
            self.assertIn("taskset -c 0 sleep 1", completed.stdout)
            self.assertFalse(output.exists())

    def test_all_cpu_trace_keeps_workload_affinity_without_cpu_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "capture"
            completed = subprocess.run(
                ["bash", SCRIPT, "--dry-run", "--all-cpus", output, "0", "--", "sleep", "1"],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertNotIn("-M 1", completed.stdout)
            self.assertIn("taskset -c 0 sleep 1", completed.stdout)
            self.assertFalse(output.exists())

    def test_missing_workload_is_rejected(self):
        completed = subprocess.run(
            ["bash", SCRIPT, "--dry-run", "/tmp/unused", "0", "--"],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("workload command is required", completed.stderr)

    def test_invalid_cpu_is_rejected(self):
        completed = subprocess.run(
            ["bash", SCRIPT, "--dry-run", "/tmp/unused", "not-a-cpu", "--", "true"],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("CPU must be a non-negative integer", completed.stderr)


if __name__ == "__main__":
    unittest.main()
