import plistlib
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import dashboard_server
from scripts import dashboard_service


class TestDashboardLaunchAgent(unittest.TestCase):
    def test_service_runs_readonly_loopback_server(self):
        c = dashboard_service.spec(Path("/opt/homebrew/bin/python3"), port=8765)
        self.assertEqual(c["ProgramArguments"][-2:], ["--port", "8765"])
        self.assertEqual(c["Label"], "com.oura-self-analysis.dashboard")
        self.assertTrue(c["KeepAlive"])
        self.assertTrue(c["RunAtLoad"])
        self.assertEqual(c["Umask"], 0o077)
        self.assertNotIn("access_token", str(c))
        self.assertNotIn("client_secret", str(c))
        self.assertEqual(plistlib.loads(plistlib.dumps(c))["Label"], c["Label"])

    def test_loaded_unchanged_service_kickstarts_without_bootout(self):
        spec = dashboard_service.spec(Path("/bin/python3"), port=8765)
        calls = []
        def fake_ctl(*args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=0)
        with patch.object(dashboard_service, "ctl", side_effect=fake_ctl):
            dashboard_service.activate_agent(spec, spec.copy())
        self.assertEqual([c[0] for c in calls], ["print", "kickstart"])
        self.assertNotIn("bootout", [c[0] for c in calls])
        self.assertNotIn("bootstrap", [c[0] for c in calls])

    def test_unloaded_service_bootstraps_and_recovers_from_race(self):
        spec = dashboard_service.spec(Path("/bin/python3"), port=8765)
        calls = []
        state = {"boots": 0}
        def fake_ctl(*args, **kwargs):
            calls.append(args[0])
            if args[0] == "print":
                return SimpleNamespace(returncode=1)
            if args[0] == "bootstrap":
                state["boots"] += 1
                return SimpleNamespace(returncode=1 if state["boots"] == 1 else 0)
            return SimpleNamespace(returncode=0)
        with patch.object(dashboard_service, "ctl", side_effect=fake_ctl), \
             patch.object(dashboard_service.time, "sleep"):
            dashboard_service.activate_agent(spec, None)
        self.assertEqual(state["boots"], 2)
        self.assertEqual(calls.count("kickstart"), 1)

    def test_port_validation(self):
        for port in (0, 80, 1023, 65536):
            with self.subTest(port=port), self.assertRaises(ValueError):
                dashboard_service.spec(Path("/bin/python3"), port=port)
        with self.assertRaises(ValueError):
            dashboard_server.serve(port=80)


if __name__ == "__main__":
    unittest.main()
