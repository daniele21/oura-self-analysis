"""Synthetic regression tests for 7v7/30v30 light/deep/REM overlaid trends."""
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import tempfile
import dashboard_server
from sleep_stage_overlays import build as overlays
from sleep_stage_trends import build as trends

END = date(2026, 10, 31)


def night(d, light=220, deep=100, rem=100):
    return {"day":d.isoformat(), "main_sleep_available":True,
            "phase_coverage":"consistent","sleep_minutes":light+deep+rem,
            "light_sleep_minutes":light,"deep_sleep_minutes":deep,
            "rem_sleep_minutes":rem}


def synthetic(n=100):
    return {(END-timedelta(days=i)).isoformat():
            night(END-timedelta(days=i),
                  light=230 if i < 7 else 190,
                  deep=110 if i < 7 else 90,
                  rem=95 if i < 7 else 105) for i in range(n)}


class StageOverlayTests(unittest.TestCase):
    def test_restrict_7_day_view_without_leaking_previous_individual_nights(self):
        data = overlays(trends(synthetic(),days=7,today=END))
        self.assertEqual(data["presets"]["7v7"]["status"],"range_too_short")
        self.assertIsNone(data["presets"]["7v7"]["reference"])
        self.assertIsNone(data["presets"]["7v7"]["recent"])
        self.assertEqual(data["presets"]["30v30"]["status"],"range_too_short")
        self.assertEqual(data["presets"]["30v30"]["required_view_days"],90)
        self.assertNotIn((END-timedelta(days=7)).isoformat(),json.dumps(data))

    def test_correct_nonoverlapping_7v7_equal_length_and_deltas(self):
        report=overlays(trends(synthetic(),days=30,today=END))
        p=report["presets"]["7v7"]
        self.assertEqual(p["status"],"available")
        self.assertEqual(p["recent"]["start"],(END-timedelta(days=6)).isoformat())
        self.assertEqual(p["reference"]["start"],(END-timedelta(days=13)).isoformat())
        self.assertEqual(p["reference"]["end"],(END-timedelta(days=7)).isoformat())
        self.assertEqual(len(p["recent"]["daily"]),7)
        self.assertEqual(len(p["reference"]["daily"]),7)
        self.assertEqual(p["recent"]["valid_nights"],7)
        self.assertEqual(p["reference"]["valid_nights"],7)
        self.assertEqual(p["recent"]["averages"]["deep"]["minutes"],110)
        self.assertEqual(p["reference"]["averages"]["deep"]["minutes"],90)
        self.assertEqual(p["delta"]["deep"]["minutes"],20)
        self.assertAlmostEqual(p["recent"]["averages"]["rem"]["percent"],round(95/435*100,2))
        self.assertEqual(p["presets"] if "presets" in p else p["code"], "7v7")

    def test_30v30_needs_90_view_and_is_not_28v28(self):
        incomplete=overlays(trends(synthetic(),days=30,today=END))
        self.assertEqual(incomplete["presets"]["30v30"]["status"],"range_too_short")
        complete=overlays(trends(synthetic(),days=90,today=END))
        p=complete["presets"]["30v30"]
        self.assertEqual(p["status"],"available")
        self.assertEqual(len(p["recent"]["daily"]),30)
        self.assertEqual(len(p["reference"]["daily"]),30)
        self.assertEqual(p["reference"]["start"],(END-timedelta(days=59)).isoformat())
        self.assertEqual(p["recent"]["start"],(END-timedelta(days=29)).isoformat())
        self.assertEqual(p["recent"]["end"],END.isoformat())
        self.assertEqual(p["recent"]["valid_nights"],30)

    def test_weighted_stage_percentages_differ_from_unweighted_mean(self):
        rows=synthetic()
        rows[END.isoformat()]=night(END,light=600,deep=100,rem=100)
        for i in range(1,7):
            d=END-timedelta(days=i)
            rows[d.isoformat()]=night(d,light=100,deep=100,rem=100)
        report=overlays(trends(rows,days=30,today=END))
        p=report["presets"]["7v7"]
        self.assertEqual(p["recent"]["averages"]["light"]["minutes"],round(1200/7,2))
        self.assertAlmostEqual(p["recent"]["averages"]["light"]["percent"],
                               round(1200/(800+6*300)*100,2))
        self.assertNotAlmostEqual(p["recent"]["averages"]["light"]["percent"],
             round((600/800*100+6*100/300*100)/7,2))

    def test_missing_nights_are_gaps_not_zero_and_suppress_delta(self):
        rows=synthetic()
        for i in (0,1,2,3):
            rows.pop((END-timedelta(days=i)).isoformat())
        report=overlays(trends(rows,days=30,today=END))
        # Anchors to the latest qualified night, which is D-4.
        self.assertEqual(report["as_of_day"],(END-timedelta(days=4)).isoformat())
        p=report["presets"]["7v7"]
        self.assertEqual(p["recent"]["end"],report["as_of_day"])
        # Add gaps within the anchored 7-day reference window.
        for i in (7,8,9,10):
            rows.pop((END-timedelta(days=i)).isoformat())
        result=overlays(trends(rows,days=30,today=END))["presets"]["7v7"]
        self.assertEqual(result["status"],"insufficient")
        self.assertEqual(result["reference"]["valid_nights"],3)
        self.assertIsNone(result["delta"]["deep"]["minutes"])
        self.assertTrue(any(not item["valid"] for item in result["reference"]["daily"]))
        self.assertTrue(all(item["deep_minutes"] is None for item in
                            result["reference"]["daily"] if not item["valid"]))

    def test_stale_last_night_detected_without_changing_window(self):
        rows=synthetic()
        for i in range(5):
            rows.pop((END-timedelta(days=i)).isoformat())
        report=overlays(trends(rows,days=90,today=END))
        self.assertEqual(report["as_of_day"],(END-timedelta(days=5)).isoformat())
        self.assertEqual(report["presets"]["30v30"]["recent"]["end"],
                         report["as_of_day"])
        self.assertEqual(report["presets"]["30v30"]["recent"]["calendar_days"],30)

    def test_qualifies_all_three_phases_or_excludes_entire_night(self):
        rows=synthetic()
        day=(END-timedelta(days=8)).isoformat()
        rows[day]["rem_sleep_minutes"]=None
        report=overlays(trends(rows,days=30,today=END))
        b=report["presets"]["7v7"]["reference"]
        self.assertEqual(b["valid_nights"],6)
        n=next(x for x in b["daily"] if x["day"]==day)
        self.assertFalse(n["valid"])
        self.assertIsNone(n["light_minutes"])
        self.assertIsNone(n["deep_percent"])

    def test_backend_api_with_30_days_and_raw_ids_not_exposed(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/"mock.sqlite3"
            with sqlite3.connect(db) as conn:
                conn.execute("""CREATE TABLE records(
                  collection TEXT,record_id TEXT,day TEXT,payload TEXT,synced_at TEXT,
                  PRIMARY KEY(collection,record_id))""")
                for i in range(75):
                    d=(END-timedelta(days=i)).isoformat()
                    payload={"type":"long_sleep","id":"NEVER_SHOW_PRIVATE_ID",
                             "total_sleep_duration":420*60,
                             "light_sleep_duration":220*60,
                             "deep_sleep_duration":100*60,
                             "rem_sleep_duration":100*60,
                             "average_hrv":50,"lowest_heart_rate":55}
                    conn.execute("INSERT INTO records VALUES (?,?,?,?,?)",
                          ("sleep",str(i),d,json.dumps(payload),
                           "2026-10-31T12:00:00Z"))
            view=dashboard_server.make_payload(db,days=30,today=END)
            out=view["sleep_intelligence"]["stage_trends"]["overlays"]
            self.assertEqual(out["presets"]["7v7"]["status"],"available")
            self.assertEqual(out["presets"]["30v30"]["status"],"range_too_short")
            self.assertNotIn("NEVER_SHOW_PRIVATE_ID",json.dumps(view))
            short=dashboard_server.make_payload(db,days=7,today=END)
            self.assertIsNone(short["sleep_intelligence"]["stage_trends"]["overlays"]["presets"]["7v7"]["reference"])
            long=dashboard_server.make_payload(db,days=90,today=END)
            self.assertEqual(long["sleep_intelligence"]["stage_trends"]["overlays"]["presets"]["30v30"]["status"],
                             "available")


if __name__=="__main__":
    unittest.main()
