import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "tools" / "run_firefox_probe.sh"
PAGE = ROOT / "workloads" / "real" / "firefox_probe" / "index.html"


class FirefoxProbeTests(unittest.TestCase):
    def test_probe_page_is_local_and_deterministic(self):
        page = PAGE.read_text(encoding="utf-8")

        self.assertIn("AutoScheduler Foreground Probe", page)
        self.assertIn("requestAnimationFrame", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("http://", page)

    def test_dry_run_uses_isolated_profile_display_and_timeout(self):
        completed = subprocess.run(
            ["bash", SCRIPT, "--dry-run", "8"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("DISPLAY=:0", completed.stdout)
        self.assertIn("XAUTHORITY=", completed.stdout)
        self.assertIn("timeout --signal=TERM --kill-after=3s 8s", completed.stdout)
        self.assertIn("firefox-esr --no-remote --new-instance --profile", completed.stdout)
        self.assertIn("file://", completed.stdout)

    def test_invalid_duration_is_rejected(self):
        completed = subprocess.run(
            ["bash", SCRIPT, "--dry-run", "zero"],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("duration must be a positive integer", completed.stderr)

    def test_dry_run_accepts_multiple_local_tabs(self):
        completed = subprocess.run(
            ["bash", SCRIPT, "--dry-run", "--tabs", "3", "8"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("tabs=3", completed.stdout)
        self.assertEqual(completed.stdout.count("file://"), 3)


if __name__ == "__main__":
    unittest.main()
