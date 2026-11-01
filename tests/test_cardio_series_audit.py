"""Synthetic, offline coverage audit tests. No personal health data."""
from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.audit_cardio_series import audit, _write_private


class TestCardioAudit(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.db = self.dir / "mock.sqlite3"
        self.end = date(2026, 11, 1)
        with sqlite3.connect(self.db) as con:
            con.execute(
                "CREATE TABLE records (collection TEXT, record_id TEXT, day TEXT, "
                "payload TEXT, synced_at TEXT, PRIMARY KEY(collection,record_id))"
            )

    def write(self, lag, row, kind="sleep"):
        day = (self.end-timedelta(days=lag)).isoformat()
        with sqlite3.connect(self.db) as con:
            con.execute("INSERT INTO records VALUES (?, ?, ?, ?, ?)", (
                kind, f"secret-{kind}-{lag}", day, json.dumps(row),
                "2026-11-01T09:00:00Z"
            ))

    def test_presence_nulls_quality_and_privacy(self):
        self.write(0, {
            "id": "private-id", "type": "long_sleep",
            "heart_rate": {"timestamp": "2026-10-31T23:00:00+01:00",
                           "interval": 300, "items": [50, None, 54, 400, 58]},
            "hrv": {"timestamp": "2026-10-31T23:00:00+01:00",
                    "interval": 300, "items": [40, None, 47, 45]},
        })
        self.write(1, {"type": "long_sleep", "heart_rate": None, "hrv": None})
        self.write(2, {"type": "rest", "heart_rate": {"interval": 300, "items": [44]}})
        report = audit(self.db, days=7, today=self.end)
        self.assertEqual(report["long_sleep_sessions_checked"], 2)
        hr = report["channels"]["heart_rate"]
        self.assertEqual(hr["schema_valid_nights"], 1)
        self.assertEqual(hr["missing_nights"], 1)
        self.assertEqual(hr["valid_samples"], 3)
        self.assertEqual(hr["invalid_samples"], 1)
        self.assertEqual(hr["null_samples"], 1)
        self.assertEqual(hr["interval_class_counts"]["300s"], 1)
        self.assertEqual(report["channels"]["hrv"]["valid_samples"], 3)
        string = json.dumps(report)
        for private in ("private-id", "secret-sleep-0", "2026-10-31T23:00:00", '"items"', '"50"'):
            self.assertNotIn(private, string)

    def test_missing_or_invalid_sample_returns_no_false_positive(self):
        self.write(0, {"type": "long_sleep", "heart_rate": {
            "interval": 0, "timestamp": "bad", "items": [40]}})
        r = audit(self.db, today=self.end, days=7)
        self.assertEqual(r["channels"]["heart_rate"]["schema_invalid_nights"], 1)
        self.assertEqual(r["channels"]["hrv"]["missing_nights"], 1)
        self.assertEqual(r["channels"]["heart_rate"]["schema_valid_nights"], 0)

    def test_no_database_rejects_and_days_are_bounded(self):
        with self.assertRaises(FileNotFoundError):
            audit(self.dir / "missing.sqlite3", today=self.end)
        with self.assertRaises(ValueError):
            audit(self.db, days=365, today=self.end)

    def test_private_file_atomic_writes(self):
        path = self.dir / "audit" / "report.json"
        _write_private(path, {"test": True})
        self.assertEqual(json.loads(path.read_text()), {"test": True})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        _write_private(path, {"test": False})
        self.assertFalse(json.loads(path.read_text())["test"])


if __name__ == "__main__":
    unittest.main()
