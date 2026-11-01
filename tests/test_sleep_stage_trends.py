"""Synthetic tests for Oura light/deep/REM longitudinal stage trends."""
from datetime import date,timedelta
import json
import unittest
from pathlib import Path
import sqlite3
import tempfile

import sleep_stage_trends as stages
import dashboard_server


class TestSleepStageTrends(unittest.TestCase):
    END=date(2026,10,31)

    @staticmethod
    def night(day,light=240,deep=100,rem=110,*,flag="consistent"):
        return {"day":day.isoformat(),"main_sleep_available":True,
                "sleep_minutes":light+deep+rem,
                "light_sleep_minutes":light,
                "deep_sleep_minutes":deep,
                "rem_sleep_minutes":rem,"phase_coverage":flag}

    def rows(self,days=35):
        return {(self.END-timedelta(days=i)).isoformat():
                self.night(self.END-timedelta(days=i),deep=100+i)
                for i in range(days)}

    def test_rolling7_uses_calendar_days_and_prior_window_history(self):
        data=stages.build(self.rows(40),days=7,today=self.END)
        self.assertEqual(len(data["daily"]),7)
        self.assertEqual(len(data["rolling7"]),7)
        self.assertEqual(data["rolling7"][0]["valid_nights"],7)
        self.assertEqual(data["rolling7"][0]["deep_minutes"],110)
        self.assertEqual(data["rolling7"][-1]["deep_minutes"],103)
        self.assertEqual(data["recent7"]["deep_minutes"],103)
        self.assertEqual(data["previous7"]["deep_minutes"],110)
        self.assertEqual(data["delta7"]["deep"]["minutes"],-7)

    def test_stage_percentages_weight_by_sleep_minutes_not_night_percent(self):
        r=self.rows(16)
        r[self.END.isoformat()]=self.night(self.END,light=600,deep=100,rem=100)
        for i in range(1,7):
            d=self.END-timedelta(days=i)
            r[d.isoformat()]=self.night(d,light=100,deep=100,rem=100)
        out=stages.build(r,days=7,today=self.END)
        self.assertAlmostEqual(out["recent7"]["light_percent"],round((600+6*100)/(800+6*300)*100,2))
        self.assertAlmostEqual(out["recent7"]["light_minutes"],round((600+6*100)/7,2))
        self.assertEqual(out["rolling7"][-1]["valid_nights"],7)

    def test_inconsistent_missing_zero_and_bool_are_excluded(self):
        r=self.rows(15)
        r[self.END.isoformat()]["phase_coverage"]="inconsistent"
        r[(self.END-timedelta(days=1)).isoformat()]["deep_sleep_minutes"]=None
        r[(self.END-timedelta(days=2)).isoformat()]["rem_sleep_minutes"]=True
        r[(self.END-timedelta(days=3)).isoformat()]["main_sleep_available"]=False
        report=stages.build(r,days=7,today=self.END)
        self.assertEqual(report["recent7"]["valid_nights"],3)
        self.assertIsNone(report["recent7"]["light_minutes"])
        self.assertIsNone(report["recent7"]["light_percent"])
        self.assertIsNone(report["rolling7"][-1]["rem_minutes"])
        self.assertFalse(report["daily"][-1]["valid"])
        self.assertIsNone(report["daily"][-1]["deep_minutes"])
        self.assertIsNone(report["delta7"]["deep"]["minutes"])

    def test_90d_weekly_buckets_and_incomplete_last_bucket(self):
        out=stages.build(self.rows(100),days=90,today=self.END)
        self.assertEqual(len(out["daily"]),90)
        self.assertEqual(len(out["rolling7"]),90)
        self.assertEqual(len(out["weekly_buckets"]),13)
        self.assertEqual(out["weekly_buckets"][-1]["calendar_days"],6)
        self.assertEqual(out["weekly_buckets"][-1]["valid_nights"],6)
        self.assertEqual(out["weekly_buckets"][0]["calendar_days"],7)
        self.assertEqual(out["weekly_buckets"][0]["start"],(self.END-timedelta(days=89)).isoformat())
        self.assertTrue(all("id" not in row for row in out["daily"]))

    def test_no_history_does_not_fabricate_trend(self):
        r={self.END.isoformat():self.night(self.END)}
        out=stages.build(r,days=30,today=self.END)
        self.assertEqual(len(out["daily"]),30)
        self.assertFalse(out["daily"][0]["valid"])
        self.assertIsNone(out["rolling7"][-1]["deep_minutes"])
        self.assertIsNone(out["delta7"]["deep"]["percentage_points"])

    def test_api_integration_synthetic_main_nights_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"fake.sqlite"
            with sqlite3.connect(db) as conn:
                conn.execute("""CREATE TABLE records (collection TEXT,record_id TEXT,
                    day TEXT,payload TEXT,synced_at TEXT,
                    PRIMARY KEY(collection,record_id))""")
                for i in range(50):
                    day=self.END-timedelta(days=i)
                    payload={"type":"long_sleep","id":"DO-NOT-LEAK",
                             "total_sleep_duration":450*60,
                             "light_sleep_duration":240*60,
                             "deep_sleep_duration":100*60,
                             "rem_sleep_duration":110*60,
                             "efficiency":92,"average_hrv":50,
                             "lowest_heart_rate":50}
                    conn.execute("INSERT INTO records VALUES(?,?,?,?,?)",
                        ("sleep",f"private-{i}",day.isoformat(),
                         json.dumps(payload),"2026-10-31T12:00:00Z"))
            payload=dashboard_server.make_payload(db,days=30,today=self.END)
            trend=payload["sleep_intelligence"]["stage_trends"]
            self.assertEqual(trend["recent7"]["valid_nights"],7)
            self.assertEqual(trend["daily"][-1]["light_minutes"],240)
            self.assertEqual(trend["daily"][-1]["deep_minutes"],100)
            self.assertEqual(trend["daily"][-1]["rem_minutes"],110)
            self.assertEqual(trend["recent7"]["rem_percent"],round(110/450*100,2))
            self.assertNotIn("DO-NOT-LEAK",json.dumps(trend))
            self.assertEqual(payload["range"]["days"],30)


if __name__=="__main__":
    unittest.main()
