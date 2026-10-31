"""Offline and synthetic tests for Sleep Intelligence 2.0. No private data."""
from datetime import date,timedelta
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

import sleep_intelligence as sleep
import health_analytics as health
import dashboard_server


class TestSleepIntelligence(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.db=Path(t.name)/"synthetic.sqlite3"
        self.today=date(2026,10,31)
        with sqlite3.connect(self.db) as conn:
            conn.execute("""CREATE TABLE records(
                collection TEXT, record_id TEXT, day TEXT, payload TEXT,
                synced_at TEXT, PRIMARY KEY(collection,record_id))""")

    def store(self,kind,lag,payload,suffix="0"):
        day=(self.today-timedelta(days=lag)).isoformat()
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)",
                         (kind,f"{kind}-{day}-{suffix}",day,json.dumps(payload),
                          "2026-10-31T09:00:00Z"))

    def seed(self, days=35):
        for lag in range(days):
            total=8*3600 if lag<7 else 7*3600
            day=(self.today-timedelta(days=lag)).isoformat()
            self.store("sleep",lag,{
                "id":"private-id-"+day,"type":"long_sleep",
                "total_sleep_duration":total,
                "time_in_bed":total+2400,
                "awake_time":1800,
                "deep_sleep_duration":total//4,
                "rem_sleep_duration":total//4,
                "light_sleep_duration":total//2,
                "efficiency":92,"latency":600,
                "average_hrv":50,"lowest_heart_rate":49,
                "average_heart_rate":54,"average_breath":14,
                "restless_periods":9,
                "bedtime_start":"2026-10-29T23:40:00+02:00",
                "bedtime_end":"2026-10-30T08:00:00+02:00",
            })
            self.store("daily_sleep",lag,{"score":82})
            self.store("daily_readiness",lag,{"score":74})
            self.store("daily_activity",lag,{"score":70,"steps":6500})

    def test_weekly_duration_uses_disjoint_seven_calendar_days(self):
        self.seed()
        report=sleep.build(self.db,days=30,today=self.today)
        current=report["weekly"]["recent"]
        old=report["weekly"]["previous"]
        self.assertEqual((current["start"],current["end"]),
                         ("2026-10-25","2026-10-31"))
        self.assertEqual((old["start"],old["end"]),
                         ("2026-10-18","2026-10-24"))
        self.assertEqual(current["available_nights"],7)
        self.assertEqual(old["available_nights"],7)
        self.assertEqual(current["averages"]["sleep_minutes"],480)
        self.assertEqual(old["averages"]["sleep_minutes"],420)
        self.assertEqual(report["weekly"]["delta_recent_vs_previous"]["sleep_minutes"],60)
        self.assertTrue(current["sufficient"])
        self.assertEqual(report["latest_main_sleep_day"],self.today.isoformat())

    def test_daily_comparisons_exclude_selected_day(self):
        self.seed()
        report=sleep.build(self.db,days=7,today=self.today)
        comparison=report["daily_comparisons"][-1]
        self.assertEqual(comparison["day"],"2026-10-31")
        self.assertEqual(comparison["previous_day"],"2026-10-30")
        self.assertEqual(comparison["delta_vs_previous_day"]["sleep_minutes"],0)
        self.assertEqual(comparison["delta_vs_previous7"]["sleep_minutes"],-60/7)
        # Rounded to two places: six 480-minute nights, one 420-minute night.
        self.assertAlmostEqual(comparison["delta_vs_previous7"]["sleep_minutes"],8.57)
        self.assertEqual(comparison["previous7_counts"]["sleep_minutes"],7)
        self.assertEqual(len(report["nights"]),7)

    def test_nap_is_never_treated_as_main_sleep(self):
        self.seed(14)
        self.store("sleep",0,{"type":"rest","total_sleep_duration":60000,
                             "deep_sleep_duration":15000},suffix="nap")
        report=sleep.build(self.db,days=7,today=self.today)
        self.assertEqual(report["nights"][-1]["sleep_minutes"],480)
        self.assertEqual(report["nights"][-1]["phase_coverage"],"consistent")
        self.assertNotIn("private-id",json.dumps(report))

    def test_nap_only_marks_main_sleep_missing(self):
        self.store("sleep",0,{"type":"rest","total_sleep_duration":12000})
        self.store("daily_sleep",0,{"score":35})
        report=sleep.build(self.db,days=7,today=self.today)
        self.assertEqual(len(report["nights"]),1)
        self.assertIsNone(report["nights"][0]["sleep_minutes"])
        self.assertFalse(report["nights"][0]["main_sleep_available"])
        self.assertEqual(report["weekly"]["recent"]["available_nights"],0)
        self.assertIsNone(report["weekly"]["recent"]["averages"]["sleep_minutes"])
        self.assertIsNone(report["latest_main_sleep_day"])

    def test_missing_previous_day_not_replaced_by_previous_available_night(self):
        self.seed(14)
        with sqlite3.connect(self.db) as conn:
            conn.execute("DELETE FROM records WHERE day=?",((self.today-timedelta(days=1)).isoformat(),))
        report=sleep.build(self.db,days=7,today=self.today)
        yesterday=report["daily_comparisons"][-1]
        self.assertFalse(yesterday["previous_day_exists"])
        self.assertIsNone(yesterday["delta_vs_previous_day"]["sleep_minutes"])
        self.assertEqual(yesterday["previous7_counts"]["sleep_minutes"],6)

    def test_sparse_two_weeks_suppress_week_over_week(self):
        self.seed(14)
        with sqlite3.connect(self.db) as conn:
            for lag in (1,2,3,4,5,8,9,10,11,12):
                conn.execute("DELETE FROM records WHERE day=?",
                             ((self.today-timedelta(days=lag)).isoformat(),))
        report=sleep.build(self.db,days=7,today=self.today)
        self.assertFalse(report["weekly"]["recent"]["sufficient"])
        self.assertFalse(report["weekly"]["previous"]["sufficient"])
        self.assertIsNone(report["weekly"]["delta_recent_vs_previous"]["sleep_minutes"])

    def test_clock_circular_sd_near_midnight_and_timezones(self):
        self.assertLess(sleep.circular_clock_sd(["23:58","00:02","23:59","00:03"]),5)
        self.assertIsNone(sleep.circular_clock_sd(["23:58","00:02","00:03"]))
        self.assertIsNone(sleep.local_time("2026-10-30T23:45"))
        self.assertEqual(sleep.local_time("2026-10-30T23:45+02:00"),"23:45")
        self.assertEqual(sleep.local_time("2026-10-30T23:45Z"),"23:45")

    def test_bad_phase_totals_are_flagged_without_normalization(self):
        self.seed(7)
        self.store("sleep",0,{
           "type":"long_sleep","total_sleep_duration":28800,
           "deep_sleep_duration":3000,"rem_sleep_duration":3000,
           "light_sleep_duration":3000,"bedtime_start":"bad"})
        night=sleep.build(self.db,days=7,today=self.today)["nights"][-1]
        self.assertEqual(night["phase_coverage"],"inconsistent")
        self.assertIn("phase_totals_do_not_match_sleep",night["data_quality"])
        self.assertIsNone(night["bedtime_local"])

    def test_integrated_dashboard_7_day_range_with_private_prior_week(self):
        self.seed(61)
        payload=dashboard_server.make_payload(self.db,days=7,today=self.today)
        self.assertIn("sleep_intelligence",payload)
        report=payload["sleep_intelligence"]
        self.assertEqual(len(report["nights"]),7)
        self.assertEqual(report["weekly"]["previous"]["available_nights"],7)
        self.assertEqual(report["daily_comparisons"][-1]["previous7_counts"]["sleep_minutes"],7)
        self.assertIn("deep_sleep_minutes",payload["records"][-1])
        self.assertEqual(payload["records"][-1]["sleep_phase_coverage"],"consistent")
        self.assertNotIn("private-id",json.dumps(payload))
        self.assertNotIn("bedtime_start",json.dumps(report))
        self.assertEqual(payload["range"]["days"],7)


if __name__=="__main__":
    unittest.main()
