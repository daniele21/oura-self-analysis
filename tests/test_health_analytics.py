import csv
from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import health_analytics as health
import oura_self_analysis as oura


class TestHealthAnalytics(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "oura.sqlite3"
        with sqlite3.connect(self.path) as con:
            con.execute("""CREATE TABLE records (
              collection TEXT NOT NULL, record_id TEXT NOT NULL, day TEXT,
              payload TEXT NOT NULL, synced_at TEXT NOT NULL,
              PRIMARY KEY (collection, record_id))""")
        self.day = date(2026, 10, 30)

    def store(self, kind: str, day: date, **kwargs):
        key = day.isoformat()
        row = {"id": f"{kind}:{key}", "day": key, **kwargs}
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT OR REPLACE INTO records VALUES (?,?,?,?,?)",
                        (kind, row["id"], key, json.dumps(row), "2026-10-30T00:00:00Z"))

    def seed(self, days: int = 50):
        for back in range(days):
            d = self.day - timedelta(days=back)
            self.store("daily_sleep", d, score=78)
            self.store("sleep", d, type="long_sleep",
                       total_sleep_duration=7 * 3600, efficiency=88, latency=600,
                       bedtime_start="2026-10-29T23:50:00+02:00" if back % 2
                       else "2026-10-29T00:10:00+02:00",
                       bedtime_end="2026-10-30T07:00:00+02:00",
                       average_hrv=50, lowest_heart_rate=51,
                       average_breath=14)
            self.store("daily_readiness", d, score=80)

    def test_insufficient_history_suppresses_baseline_and_regularity(self):
        d = self.day
        self.store("sleep", d, type="long_sleep",
                   total_sleep_duration=7*3600, average_hrv=50, lowest_heart_rate=50)
        rows, document = health.analyze(self.path, 7, today=self.day)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["hrv_change_pct"])
        self.assertIsNone(rows[0]["bedtime_consistency_sd_minutes_14d"])
        self.assertIsNone(rows[0]["prior_day_training"])
        self.assertNotIn("autonomic-trends",
                         [item["id"] for item in document["insights"]])

    def test_night_time_crossing_midnight_is_stable(self):
        self.assertEqual(health.bedtime_minute("2026-10-29T23:50:00+02:00"), 710)
        self.assertEqual(health.bedtime_minute("2026-10-30T00:10:00+02:00"), 730)
        self.assertEqual(health.local_clock("2026-10-30T00:10:00+02:00"), "00:10")
        self.assertIsNone(health.bedtime_minute("2026-10-30T00:10:00"))
        self.assertIsNone(health.bedtime_minute("not-a-date"))

    def test_sleep_and_autonomic_baselines_have_valid_units(self):
        self.seed(60)
        rows, report = health.analyze(self.path, 30, today=self.day)
        self.assertEqual(len(rows), 30)
        current = rows[-1]
        self.assertEqual(current["sleep_minutes"], 420.0)
        self.assertEqual(current["sleep_latency_minutes"], 10)
        self.assertEqual(current["respiratory_rate_per_min"], 14)
        self.assertEqual(current["hrv_median_7d"], 50)
        self.assertEqual(current["hrv_median_previous_28d"], 50)
        self.assertEqual(current["rhr_change_bpm"], 0)
        self.assertLess(current["bedtime_consistency_sd_minutes_14d"], 15)
        ids = [i["id"] for i in report["insights"]]
        self.assertIn("autonomic-trends", ids)
        self.assertIn("sleep-regularity", ids)
        self.assertEqual(report["metadata"]["workout_history_available"], False)
        self.assertTrue(all(i["medical_alert"] is False for i in report["insights"]))

    def test_training_lag_uses_previous_day_and_requires_samples(self):
        self.seed(45)
        for back in (1, 3, 5, 7, 9):
            self.store("workout", self.day - timedelta(days=back),
                       activity="cross_training", intensity="hard")
        rows, doc = health.analyze(self.path, 30, today=self.day)
        self.assertTrue(rows[-1]["prior_day_training"])
        self.assertEqual(rows[-1]["training_sessions"], 0)
        training = [i for i in doc["insights"] if i["id"] == "exercise-following-day"]
        self.assertEqual(len(training), 1)
        self.assertGreaterEqual(training[0]["measurements"]["n_post_training"], 4)
        self.assertGreaterEqual(training[0]["measurements"]["n_other"], 4)
        self.assertIn("Non controlla intensità", " ".join(training[0]["limitations"]))

    def test_7_day_vs_previous28_windows_do_not_overlap(self):
        self.seed(60)
        # Latest 7 nights differ, while the previous 28 (days 7..34 ago)
        # remain at the older baseline value 50 ms.
        for back in range(7):
            d = self.day - timedelta(days=back)
            self.store("sleep", d, type="long_sleep",
                       total_sleep_duration=7*3600, average_hrv=60,
                       lowest_heart_rate=49,
                       bedtime_start="2026-10-29T23:30:00+02:00",
                       bedtime_end="2026-10-30T07:00:00+02:00")
        rows, _ = health.analyze(self.path, 30, today=self.day)
        newest = rows[-1]
        self.assertEqual(newest["hrv_median_7d"], 60)
        self.assertEqual(newest["hrv_median_previous_28d"], 50)
        self.assertEqual(newest["hrv_change_pct"], 20.0)

    def test_training_not_inferred_if_no_records(self):
        self.seed(35)
        rows, report = health.analyze(self.path, 30, today=self.day)
        self.assertIsNone(rows[-1]["training_sessions"])
        self.assertIsNone(rows[-1]["prior_day_training"])
        self.assertNotIn("exercise-following-day",
                         [i["id"] for i in report["insights"]])

    def test_invalid_hrv_is_missing_not_zero(self):
        self.seed(15)
        self.store("sleep", self.day, type="long_sleep", total_sleep_duration=7 * 3600,
                   average_hrv=-1, lowest_heart_rate=500)
        rows, _ = health.analyze(self.path, 7, today=self.day)
        self.assertIsNone(rows[-1]["hrv_ms"])
        self.assertIsNone(rows[-1]["rhr_bpm"])
        self.assertIn("missing_hrv", rows[-1]["data_quality"])

    def test_export_contains_only_daily_features_and_explanations(self):
        self.seed(45)
        csv_path, json_path, payload = health.export(
            self.path, days=30, today=self.day, output_dir=self.root / "exports")
        with csv_path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 30)
        self.assertNotIn("heart_rate", rows[-1])
        self.assertIn("evidence_urls", payload["insights"][0])
        self.assertEqual(json.loads(json_path.read_text())["schema_version"], "1.0")
        self.assertEqual(csv_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json_path.stat().st_mode & 0o777, 0o600)

    def test_sleep_insight_uses_calendar_window_not_last_seven_rows(self):
        # Four sleep nights spread across a month must not count as four
        # observations in the most recent seven calendar days.
        for back in (0, 8, 16, 24):
            self.store("sleep", self.day - timedelta(days=back),
                       type="long_sleep", total_sleep_duration=7 * 3600,
                       average_hrv=50, lowest_heart_rate=52)
        _, report = health.analyze(self.path, 30, today=self.day)
        self.assertNotIn("sleep-duration", [i["id"] for i in report["insights"]])

    def test_gaps_do_not_fabricate_observations(self):
        self.seed(8)
        rows, doc = health.analyze(self.path, 30, today=self.day)
        self.assertEqual(len(rows), 8)
        self.assertEqual(doc["metadata"]["observed_days"], 8)
        self.assertIsNone(rows[-1]["hrv_median_previous_28d"])


if __name__ == "__main__":
    unittest.main()
