"""Synthetic Exercise Recovery 2.0 tests: API-compatible records, no actual health data."""
from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import exercise_recovery as er
import health_analytics as health


class TestExerciseRecovery(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "oura.sqlite3"
        self.today = date(2026, 10, 31)
        with sqlite3.connect(self.db) as db:
            db.execute("""CREATE TABLE records(
              collection TEXT NOT NULL, record_id TEXT NOT NULL, day TEXT,
              payload TEXT NOT NULL, synced_at TEXT NOT NULL,
              PRIMARY KEY(collection,record_id))""")

    def save(self, collection, day, data, suffix="0"):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT OR REPLACE INTO records VALUES (?,?,?,?,?)",
                       (collection, f"{collection}-{day}-{suffix}", day,
                        json.dumps(data), "2026-10-31T09:00:00Z"))

    def workout(self, back, *, activity="cross_training", intensity="hard",
                start="2026-10-29T18:00:00+02:00",
                end="2026-10-29T19:00:00+02:00", label="private workout label",
                suffix="0"):
        day = (self.today-timedelta(days=back)).isoformat()
        self.save("workout",day,{"id":"secret-workout-id",
                                "activity":activity,"intensity":intensity,
                                "start_datetime":start,"end_datetime":end,
                                "source":"manual","label":label},suffix)

    def rows(self, days=60):
        return [
            {"day": (self.today-timedelta(days=i)).isoformat(),
             "hrv_ms": 50., "rhr_bpm": 55., "sleep_minutes": 420.}
            for i in range(days)
        ]

    def test_duration_timezone_and_intensity_categories(self):
        self.workout(7, activity="padel", intensity="moderate",
                     start="2026-10-29T23:30:00+02:00",
                     end="2026-10-30T00:30:00+01:00")
        result = er.read_workout_days(self.db, self.today-timedelta(days=10), self.today)
        day = (self.today-timedelta(days=7)).isoformat()
        self.assertEqual(result[day]["duration_minutes"], 120.0)
        self.assertEqual(result[day]["intensities"], {"moderate":1})
        exposure=er.daily_exposure(result, day)
        self.assertEqual(exposure["workout_activity_group"],"racket_sport")
        self.assertEqual(exposure["workout_intensity_category"],"moderate")
        self.assertEqual(exposure["workout_minutes_recorded"],120.)
        self.assertNotIn("private workout label", json.dumps(result))
        self.assertNotIn("secret-workout-id", json.dumps(result))

    def test_bad_duration_is_unknown_not_zero_or_fake_rpe(self):
        self.workout(5, intensity="hard", start="2026-10-29T23:00:00",
                     end="2026-10-29T23:30:00")
        result=er.read_workout_days(self.db,self.today-timedelta(days=10),self.today)
        day=(self.today-timedelta(days=5)).isoformat()
        agg=result[day]
        self.assertIsNone(agg["duration_minutes"])
        self.assertEqual(agg["duration_n"],0)
        exposure=er.daily_exposure(result,day)
        self.assertIsNone(exposure["workout_minutes_recorded"])
        self.assertIsNone(exposure["workout_hard_minutes_recorded"])
        self.assertEqual(exposure["workout_intensity_sessions"],1)
        self.assertNotIn("rpe",json.dumps(exposure).lower())

    def test_isolated_workouts_have_1_2_3_day_curves(self):
        for back in (9,17,25,33,41):
            self.workout(back)
        rows=self.rows()
        for back in (9,17,25,33,41):
            for lag,delta in ((1,-7),(2,-4),(3,0)):
                row=next(x for x in rows if x["day"]==
                         (self.today-timedelta(days=back-lag)).isoformat())
                row["hrv_ms"]=50+delta
                row["rhr_bpm"]=55-delta
                row["sleep_minutes"]=420-5*lag
        workouts=er.read_workout_days(self.db,self.today-timedelta(days=59),self.today)
        result=er.event_curve(rows,workouts,start=self.today-timedelta(days=59),end=self.today)
        self.assertEqual(result["eligible_isolated_days"],5)
        self.assertEqual(result["observed_event_days"],5)
        self.assertEqual(result["excluded_overlapping_days"],0)
        self.assertEqual([p["hrv_ms_delta_median"] for p in result["outcomes"]],[-7.,-4.,0.])
        self.assertEqual([p["rhr_bpm_delta_median"] for p in result["outcomes"]],[7.,4.,0.])
        self.assertEqual(result["outcomes"][0]["hrv_ms_n"],5)
        self.assertEqual(result["by_activity"][0]["activity"],"cross_training")
        self.assertEqual(result["by_activity"][0]["observed_days"],5)
        self.assertEqual(result["by_intensity"][0]["intensity"],"hard")
        self.assertTrue(all(x["medical_alert"] is False for x in er.recovery_insights(result)))

    def test_frequent_workouts_show_overlapping_cohort_not_isolated(self):
        for back in (9,10,24,25):
            self.workout(back)
        workouts=er.read_workout_days(self.db,self.today-timedelta(days=59),self.today)
        result=er.event_curve(self.rows(),workouts,start=self.today-timedelta(days=59),end=self.today)
        self.assertEqual(result["eligible_isolated_days"],0)
        self.assertEqual(result["observed_event_days"],4)
        self.assertEqual(result["excluded_overlapping_days"],4)
        self.assertEqual(result["outcomes"][0]["hrv_ms_delta_median"],None)
        self.assertEqual(result["observed_outcomes"][0]["hrv_ms_delta_median"],0)
        self.assertEqual(result["quality"],"observational-overlap")
        self.assertIn("allenamenti ravvicinati", er.recovery_insights(result)[0]["summary"])

    def test_recent_immature_event_and_old_boundary_are_excluded(self):
        for back in (1, 59):
            self.workout(back)
        workout=er.read_workout_days(self.db,self.today-timedelta(days=62),self.today)
        result=er.event_curve(self.rows(),workout,start=self.today-timedelta(days=59),end=self.today)
        self.assertEqual(result["excluded_recent_days"],1)
        self.assertEqual(result["eligible_isolated_days"],1)
        self.assertEqual(result["observed_outcomes"][0]["hrv_ms_n"],1)
        self.assertIsNone(result["observed_outcomes"][0]["hrv_ms_delta_median"])

    def test_actual_analytics_integration_with_only_7_visible_rows(self):
        for back in (9,17,25,33,41):
            self.workout(back)
        for back in range(61):
            day=(self.today-timedelta(days=back)).isoformat()
            self.save("sleep",day,{"id":"main","type":"long_sleep",
                    "total_sleep_duration":420*60,"average_hrv":50+back%3,
                    "lowest_heart_rate":51+back%3})
            self.save("daily_sleep",day,{"score":78})
        rows, report=health.analyze(self.db,days=7,today=self.today)
        self.assertEqual(len(rows),7)
        self.assertEqual(report["schema_version"],"1.4")
        self.assertEqual(report["exercise_recovery"]["eligible_isolated_days"],5)
        self.assertTrue(all(x["day"]>=(self.today-timedelta(days=6)).isoformat()
                            for x in rows))
        self.assertTrue(any(i["id"]=="exercise-recovery-72h" for i in report["insights"]))

    def test_missing_workouts_never_equal_verified_rest(self):
        self.assertIsNone(er.daily_exposure({}, self.today.isoformat())["workout_minutes_recorded"])
        self.assertEqual(er.category("random secret label"),"other")
        self.assertIsNone(er.duration_minutes({"start_datetime":"invalid", "end_datetime":"invalid"}))


if __name__ == "__main__":
    unittest.main()
