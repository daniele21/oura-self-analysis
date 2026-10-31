import plistlib
from pathlib import Path
import unittest

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

    def test_port_validation(self):
        for port in (0, 80, 1023, 65536):
            with self.subTest(port=port), self.assertRaises(ValueError):
                dashboard_service.spec(Path("/bin/python3"), port=port)
        with self.assertRaises(ValueError):
            dashboard_server.serve(port=80)


if __name__ == "__main__":
    unittest.main()
