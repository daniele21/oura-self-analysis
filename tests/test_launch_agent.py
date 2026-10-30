import unittest
from pathlib import Path
from scripts.install_launch_agent import job_spec


class TestLaunchAgent(unittest.TestCase):
    def test_job_runs_the_local_pipeline_without_secrets(self):
        spec = job_spec("/opt/homebrew/bin/uv",
                        Path("/Users/example/Library/CloudStorage/GoogleDrive-example/My Drive/Oura Self Analysis"),
                        hour=9, minute=15, days=30)
        self.assertEqual(spec["StartCalendarInterval"], {"Hour": 9, "Minute": 15})
        self.assertFalse(spec["RunAtLoad"])
        self.assertIn("local_enrichment.py", " ".join(spec["ProgramArguments"]))
        self.assertIn("run", spec["ProgramArguments"])
        self.assertNotIn("access_token", str(spec))
        self.assertNotIn("client_secret", str(spec))

    def test_invalid_settings_rejected(self):
        for hour, minute, days in ((24, 0, 30), (9, -1, 30), (9, 15, 0), (9, 15, 100)):
            with self.subTest(hour=hour, minute=minute, days=days):
                with self.assertRaises(ValueError):
                    job_spec("/usr/local/bin/uv", Path("/tmp/drive"), hour, minute, days)


if __name__ == "__main__":
    unittest.main()
