"""Tests use only synthetic data: never import personal Oura health records."""
from contextlib import contextmanager
from datetime import date, timedelta
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

import dashboard_server
import oura_self_analysis as oura


class TestPrivateDashboard(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.db = self.folder / "synthetic.sqlite3"
        with sqlite3.connect(self.db) as con:
            con.execute("""CREATE TABLE records (
              collection TEXT NOT NULL, record_id TEXT NOT NULL, day TEXT,
              payload TEXT NOT NULL, synced_at TEXT NOT NULL,
              PRIMARY KEY (collection, record_id))""")
        self.today = date.today()

    def insert(self, kind, day, **fields):
        record = {"id": f"{kind}-{day}", "day": day, **fields}
        with sqlite3.connect(self.db) as con:
            con.execute(
                "INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?, ?)",
                (kind, record["id"], day, json.dumps(record), "2026-10-30T12:00:00Z"))

    def seed(self, days=55):
        for i in range(days):
            day = (self.today - timedelta(days=i)).isoformat()
            self.insert("daily_sleep", day, score=82)
            self.insert("daily_readiness", day, score=77)
            self.insert("daily_activity", day, score=79, steps=7100+i)
            self.insert("sleep", day, type="long_sleep",
                        total_sleep_duration=26400,
                        average_hrv=47+i/10, lowest_heart_rate=52,
                        bedtime_start="2026-10-29T23:30:00+02:00",
                        bedtime_end="2026-10-30T07:10:00+02:00",
                        efficiency=91, average_breath=14.6, latency=500)
        for i in (1, 3, 5, 7, 9, 11, 13, 15):
            self.insert("workout", (self.today - timedelta(days=i)).isoformat(),
                        activity="cross_training", calories=180)

    @contextmanager
    def server(self):
        httpd = dashboard_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), dashboard_server.DashboardHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield httpd.server_port
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)

    @staticmethod
    def request(port, method="GET", path="/api/dashboard?days=30", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            conn.request(method, path, headers=headers or {})
            res = conn.getresponse()
            body = res.read()
            return res.status, dict(res.getheaders()), body
        finally:
            conn.close()

    def test_mobile_api_uses_real_sqlite_derived_fields(self):
        self.seed()
        payload = dashboard_server.make_payload(self.db, days=30, today=self.today)
        self.assertEqual(payload["meta"]["observed_days"], 30)
        self.assertEqual(payload["meta"]["age_days"], 0)
        self.assertEqual(payload["records"][-1]["steps"], 7100)
        self.assertEqual(payload["records"][-1]["sleep_minutes"], 440)
        self.assertEqual(payload["records"][-1]["readiness_score"], 77)
        self.assertEqual(payload["records"][-1]["hrv_ms"], 47)
        self.assertEqual(payload["records"][-1]["training_sessions"], 0)
        self.assertTrue(payload["meta"]["workout_history_available"])
        self.assertIn("limitations", payload["insights"][0])
        self.assertNotIn("payload", payload["records"][-1])
        self.assertNotIn("access_token", json.dumps(payload))
        self.assertEqual(payload["range"]["days"], 30)
        recovery = payload["exercise_recovery"]
        self.assertIsInstance(recovery, dict)
        self.assertEqual(len(recovery["outcomes"]), 3)
        self.assertEqual(len(recovery["observed_outcomes"]), 3)
        self.assertEqual(recovery["method"], "recorded-workout-isolated-wake-day-lag")
        self.assertIn("workout_minutes_recorded", payload["records"][-1])
        self.assertNotIn("record_id", json.dumps(recovery))
        self.assertNotIn("start_datetime", json.dumps(recovery))
        self.assertNotIn("end_datetime", json.dumps(recovery))

    def test_90_day_range_has_honest_coverage(self):
        self.seed(days=25)
        payload = dashboard_server.make_payload(self.db, days=90, today=self.today)
        self.assertEqual(payload["meta"]["observed_days"], 25)
        self.assertEqual(payload["meta"]["coverage_percent"], 28)
        self.assertEqual(payload["range"]["days"], 90)

    def test_api_security_and_content_type(self):
        self.seed()
        with patch.object(oura, "DB_PATH", self.db), self.server() as port:
            status, headers, body = self.request(port)
            self.assertEqual(status, 200)
            result = json.loads(body)
            self.assertEqual(len(result["records"]), 30)
            self.assertEqual(headers.get("Cache-Control"), "no-store")
            self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
            self.assertIn("frame-ancestors 'none'", headers.get("Content-Security-Policy", ""))
            self.assertNotIn("Set-Cookie", headers)
            self.assertNotIn("access_token", body.decode())

            status, _, _ = self.request(port, path="/api/dashboard?days=365")
            self.assertEqual(status, 400)
            status, _, _ = self.request(port, path="/api/dashboard?days=30&unused=1")
            self.assertEqual(status, 400)
            status, _, _ = self.request(port, path="/../../oura.sqlite3")
            self.assertEqual(status, 404)
            status, _, _ = self.request(port, path="/PRIVACY.md")
            self.assertEqual(status, 404)
            status, _, _ = self.request(port, headers={"Host": "evil.example"})
            self.assertEqual(status, 403)
            status, _, _ = self.request(port, method="POST")
            self.assertEqual(status, 405)

            status, headers, body = self.request(port, path="/")
            self.assertEqual(status, 200)
            self.assertIn(b"Oura", body)
            self.assertEqual(headers.get("Cache-Control"), "no-store")
            status, _, body = self.request(port, path="/app.js")
            self.assertEqual(status, 200)
            self.assertIn(b"function trendsView", body)
            status, _, body = self.request(port, path="/manifest.webmanifest")
            self.assertEqual(status, 200)
            self.assertIn(b"standalone", body)

    def test_no_data_does_not_fake_metrics(self):
        with patch.object(oura, "DB_PATH", self.db), self.server() as port:
            status, _, body = self.request(port)
            self.assertEqual(status, 503)
            self.assertTrue(json.loads(body)["retryable"])

    def test_bad_range_is_rejected(self):
        for days in (-5, 0, 365):
            with self.subTest(days=days), self.assertRaises(ValueError):
                dashboard_server.make_payload(self.db, days=days, today=self.today)


if __name__ == "__main__":
    unittest.main()
