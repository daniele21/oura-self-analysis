"""Offline, synthetic regression tests for shared period comparison analytics."""
from datetime import date, timedelta
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

import period_comparisons as pc
import dashboard_server
from scripts.validate_oura_insights import audit, private_write


END = date(2026, 10, 31)


def dated(lag):
    return (END - timedelta(days=lag)).isoformat()


def make_rows(n=60):
    rows = []
    for lag in range(n):
        rows.append({
            "day": dated(lag), "main_sleep_available": True,
            "sleep_minutes": 480 if lag < 7 else 420,
            "sleep_efficiency_pct": 94 if lag < 7 else 90,
            "sleep_score": 80,
            "awake_minutes": 22, "sleep_latency_minutes": 11,
            "deep_sleep_minutes": 110, "rem_sleep_minutes": 100,
            "light_sleep_minutes": 270 if lag < 7 else 210,
            "bedtime_local": "23:55" if lag % 2 else "00:05",
            "wake_local": "07:45",
            "hrv_ms": 45 if lag < 7 else 60,
            "rhr_bpm": 55 if lag < 7 else 48,
            "respiratory_rate_per_min": 14,
            "private_field": "NEVER EXPOSE",
        })
    return rows


def metric(report, window, key):
    return next(m for m in report["windows"][window]["metrics"] if m["key"] == key)


class TestPeriodComparisons(unittest.TestCase):
    def test_windows_are_disjoint_and_time_aligned(self):
        report = pc.build(make_rows(), today=END, group="sleep")
        recent = metric(report, "7v7", "sleep_minutes")
        self.assertEqual(recent["recent"]["start"], dated(6))
        self.assertEqual(recent["recent"]["end"], dated(0))
        self.assertEqual(recent["reference"]["start"], dated(13))
        self.assertEqual(recent["reference"]["end"], dated(7))
        self.assertEqual(recent["delta"], 60)
        self.assertEqual(metric(report, "7v28", "sleep_minutes")["delta"], 60)
        self.assertEqual(metric(report, "28v28", "sleep_minutes")["delta"], 15)
        self.assertEqual(recent["persistence"]["same_direction_n"], 7)
        self.assertEqual(recent["persistence"]["longest_calendar_run"], 7)

    def test_recovery_uses_medians_and_nonoverlapping_7_28(self):
        report = pc.build(make_rows(), today=END, group="recovery")
        hrv = metric(report, "7v28", "hrv_ms")
        hr = metric(report, "7v28", "rhr_bpm")
        self.assertEqual((hrv["recent"]["value"], hrv["reference"]["value"]), (45, 60))
        self.assertEqual(hrv["delta"], -15)
        self.assertEqual(hr["delta"], 7)
        self.assertEqual(hrv["reference"]["end"], dated(7))
        self.assertIsNone(hrv["shift_in_baseline_spreads"])  # Constant baseline, no z-score.

    def test_missing_is_not_zero_and_breaks_consecutive_run(self):
        rows=make_rows()
        rows=[r for r in rows if r["day"] not in (dated(3), dated(8), dated(9), dated(10), dated(11))]
        result=pc.build(rows,today=END,group="sleep")
        duration=metric(result,"7v7","sleep_minutes")
        self.assertEqual(duration["recent"]["valid_nights"],6)
        self.assertEqual(duration["reference"]["valid_nights"],3)
        self.assertIsNone(duration["delta"])
        self.assertEqual(duration["status"],"insufficient")
        self.assertIsNone(duration["persistence"])

    def test_nonfinite_and_bool_values_are_excluded(self):
        rows=make_rows()
        rows[0]["sleep_minutes"]=True
        rows[1]["hrv_ms"]=float("nan")
        rows[2]["hrv_ms"]=float("inf")
        result=pc.build(rows,today=END,group="recovery")
        hrv=metric(result,"7v28","hrv_ms")
        self.assertEqual(hrv["recent"]["valid_nights"],5)
        self.assertEqual(hrv["recent"]["value"],45)
        self.assertEqual(metric(pc.build(rows,today=END,group="sleep"),"7v7","sleep_minutes")["recent"]["valid_nights"],6)

    def test_sleep_score_without_main_session_cannot_count_as_night(self):
        rows=make_rows()
        rows[0]["main_sleep_available"]=False
        rows[0]["sleep_minutes"]=480
        report=pc.build(rows,today=END,group="sleep")
        score=metric(report,"7v7","sleep_score")
        self.assertEqual(score["recent"]["valid_nights"],6)

    def test_circular_clock_near_midnight(self):
        report=pc.build(make_rows(),today=END,group="sleep")
        clock=metric(report,"7v7","bedtime_local")
        self.assertIsNotNone(clock["recent"]["value"])
        self.assertLess(clock["recent"]["value"],10)
        self.assertIsNone(clock["persistence"])
        self.assertIsNone(clock["delta_percent"])


    def test_recent_tail_exposes_opposed_weekly_and_last_three_directions(self):
        rows = make_rows()
        for row in rows:
            lag = (END - date.fromisoformat(row["day"])).days
            if lag < 3:
                row["sleep_minutes"] = 360
                row["hrv_ms"] = 20
            elif lag < 7:
                row["sleep_minutes"] = 500
                row["hrv_ms"] = 50
            elif lag < 14:
                row["sleep_minutes"] = 400
                row["hrv_ms"] = 30
        sleep = pc.build(rows, today=END, group="sleep")
        weekly = metric(sleep, "7v7", "sleep_minutes")
        tail = next(m for m in sleep["recent_week_trajectory"]["metrics"]
                    if m["key"] == "sleep_minutes")
        self.assertGreater(weekly["delta"], 0)
        self.assertEqual(tail["delta"], -140)
        self.assertTrue(tail["opposes_weekly_comparison"])
        self.assertEqual(tail["latest_three"]["valid_nights"], 3)
        recovery = pc.build(rows, today=END, group="recovery")
        hr_tail = next(m for m in recovery["recent_week_trajectory"]["metrics"]
                       if m["key"] == "hrv_ms")
        self.assertEqual(hr_tail["delta"], -30)
        self.assertTrue(hr_tail["opposes_weekly_comparison"])

    def test_missing_last_three_night_suppresses_short_trajectory(self):
        rows = make_rows()
        rows = [r for r in rows if r["day"] != dated(1)]
        report = pc.build(rows, today=END, group="sleep")
        tail = next(m for m in report["recent_week_trajectory"]["metrics"]
                    if m["key"] == "sleep_minutes")
        self.assertIsNone(tail["delta"])
        self.assertIsNone(tail["opposes_weekly_comparison"])

    def test_older_daily_data_not_leaked_in_comparison_payload(self):
        report=pc.build(make_rows(),today=END,group="sleep")
        content=json.dumps(report)
        self.assertNotIn("NEVER EXPOSE",content)
        self.assertNotIn("private_field",content)
        self.assertNotIn("rows",report)
        self.assertNotIn("series",report)


class TestIntegratedDashboard(unittest.TestCase):
    def test_dashboard_7days_keeps_prior_56day_nights_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"synthetic.sqlite3"
            with sqlite3.connect(db) as con:
                con.execute("""CREATE TABLE records(
                    collection TEXT, record_id TEXT, day TEXT, payload TEXT,
                    synced_at TEXT, PRIMARY KEY(collection,record_id))""")
                for lag in range(60):
                    day=dated(lag)
                    sleep={
                        "id": "do-not-leak-"+day, "type": "long_sleep",
                        "total_sleep_duration": 28800 if lag<7 else 25200,
                        "time_in_bed": 30600, "efficiency": 92,
                        "latency": 600, "awake_time": 1800,
                        "deep_sleep_duration": 7200, "rem_sleep_duration": 7200,
                        "light_sleep_duration": 14400 if lag<7 else 10800,
                        "average_hrv": 45 if lag<7 else 60,
                        "lowest_heart_rate": 55 if lag<7 else 48,
                        "average_heart_rate": 60, "average_breath": 14,
                        "bedtime_start": day+"T23:30:00+02:00",
                        "bedtime_end": day+"T08:00:00+02:00",
                    }
                    for kind,payload in (("sleep",sleep),
                                         ("daily_sleep",{"score":80}),
                                         ("daily_readiness",{"score":75}),
                                         ("daily_activity",{"score":75,"steps":8000})):
                        con.execute("INSERT INTO records VALUES(?,?,?,?,?)",
                            (kind, kind+day, day, json.dumps(payload), "2026-10-31T12:00:00Z"))
            payload=dashboard_server.make_payload(db,days=7,today=END)
            self.assertEqual(len(payload["sleep_intelligence"]["nights"]),7)
            self.assertLessEqual(len(payload["records"]),7)
            sleep=payload["sleep_intelligence"]["comparisons"]
            recovery=payload["period_comparisons"]
            self.assertEqual(metric(sleep,"28v28","sleep_minutes")["delta"],15)
            self.assertEqual(metric(recovery,"7v28","hrv_ms")["delta"],-15)
            raw=json.dumps(payload)
            self.assertNotIn("do-not-leak",raw)
            # Older individual days (8..56) are not listed in day-level sections.
            self.assertNotIn(dated(40),json.dumps(payload["records"]))
            self.assertNotIn(dated(40),json.dumps(payload["sleep_intelligence"]["nights"]))
            # Three-day sync lag must not convert the 7d recent HRV window
            # into three valid records out of seven; anchor to the last night.
            stale = dashboard_server.make_payload(
                db, days=7, today=END + timedelta(days=3))
            self.assertEqual(stale["period_comparisons"]["as_of_day"], END.isoformat())
            self.assertEqual(
                stale["sleep_intelligence"]["comparisons"]["as_of_day"],
                END.isoformat())
            self.assertEqual(
                metric(stale["period_comparisons"], "7v28", "hrv_ms")["delta"], -15)
            self.assertEqual(
                metric(stale["sleep_intelligence"]["comparisons"], "7v7", "sleep_minutes")["delta"], 60)
            # Browser only sees the selected seven calendar days; earlier
            # individual Oura records remain hidden in both cases.
            self.assertLessEqual(len(stale["records"]), 7)
            self.assertNotIn(dated(10), json.dumps(stale["records"]))
            private_review = audit(db, today=END + timedelta(days=3))
            self.assertEqual(private_review["checks_executed"], 42)
            self.assertFalse(any(issue["code"] == "COMPARISON_INCONSISTENCY"
                                 for issue in private_review["issues"]))
            self.assertIn("DATA_NOT_CURRENT",
                          [issue["code"] for issue in private_review["issues"]])
            review_path = Path(tmp) / "private-qa.json"
            private_write(review_path, private_review)
            self.assertEqual(review_path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("do-not-leak", review_path.read_text())



if __name__=="__main__":
    unittest.main()
