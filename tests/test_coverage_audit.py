import json
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.audit_oura_coverage import audit


class TestCoverageAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "oura.sqlite3"
        self.day = date(2026, 10, 31)
        with sqlite3.connect(self.db) as conn:
            conn.execute("""CREATE TABLE records (
              collection TEXT NOT NULL, record_id TEXT NOT NULL, day TEXT,
              payload TEXT NOT NULL, synced_at TEXT NOT NULL,
              PRIMARY KEY(collection, record_id))""")

    def row(self, collection, back, payload):
        day = (self.day - timedelta(days=back)).isoformat()
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT OR REPLACE INTO records VALUES(?, ?, ?, ?, ?)",
                         (collection, f"{collection}-{back}", day,
                          json.dumps(payload), "2026-10-31T01:00:00Z"))

    def test_counts_only_no_values_or_ids(self):
        self.row("sleep",0,{"type":"long_sleep","average_hrv":67.123,
                            "lowest_heart_rate":47,"total_sleep_duration":28800,
                            "bedtime_start":"2026-10-30T23:01+01:00"})
        self.row("sleep",1,{"type":"rest","average_hrv":67.123,
                            "lowest_heart_rate":45})
        self.row("workout",2,{"activity":"cross_training","start_datetime":"secret"})
        result=audit(self.db,days=65,today=self.day)
        self.assertEqual(result["collections"]["sleep"]["records_seen"], 2)
        self.assertEqual(result["collections"]["sleep"]["observed_calendar_days"], 1)
        self.assertEqual(result["collections"]["workout"]["observed_calendar_days"], 1)
        self.assertEqual(result["collections"]["sleep"]["field_non_null_counts"]["average_hrv"],1)
        text=json.dumps(result)
        self.assertNotIn("67.123",text)
        self.assertNotIn("2026-10-30T23:01",text)
        self.assertNotIn("secret",text)
        self.assertNotIn("cross_training",text)
        self.assertFalse(result["readiness"]["recent_7_and_prior_28_possible_from_total_sleep_count"])

    def test_invalid_json_is_not_fatal(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT INTO records VALUES(?, ?, ?, ?, ?)",
                         ("daily_sleep","bad","2026-10-30","{invalid", "2026-10-31"))
        result=audit(self.db,days=35,today=self.day)
        self.assertEqual(result["collections"]["daily_sleep"]["invalid_json_records"],1)
        self.assertEqual(result["collections"]["daily_sleep"]["observed_calendar_days"],0)

    def test_reject_unbounded_audit(self):
        for days in (0, 7, 365):
            with self.subTest(days=days),self.assertRaises(ValueError):
                audit(self.db,days=days,today=self.day)


if __name__ == "__main__":
    unittest.main()
