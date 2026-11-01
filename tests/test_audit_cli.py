"""Audit CLIs must work from repo root as scripts and modules."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestAuditCli(unittest.TestCase):
    def test_direct_invocation_and_module_import(self):
        for name in ("audit_cardio_series", "audit_oura_coverage"):
            for command in (
                [sys.executable, f"scripts/{name}.py", "--help"],
                [sys.executable, "-m", f"scripts.{name}", "--help"],
            ):
                with self.subTest(command=command):
                    completed = subprocess.run(
                        command, cwd=ROOT, capture_output=True, text=True, timeout=8,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr[:300])
                    self.assertIn("--days", completed.stdout)


if __name__ == "__main__":
    unittest.main()
