"""Synthetic tests for exact previous night, prior-seven profiles and night halves."""
from datetime import date, timedelta, datetime
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cardio_night_comparisons import comparison


class TestCardioNightComparisons(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "synthetic.sqlite3"
        self.end = date(2026, 10, 31)
        with sqlite3.connect(self.db) as con:
            con.execute("""CREATE TABLE records (
                collection TEXT, record_id TEXT, day TEXT, payload TEXT,
                synced_at TEXT, PRIMARY KEY(collection,record_id))""")

    def insert(self, lag, *, heart=50, hrv=40, hours=8, note="secret"):
        day = self.end - timedelta(days=lag)
        base = datetime.fromisoformat((day - timedelta(days=1)).isoformat() + "T23:00:00+01:00")
        count = hours * 12
        series = lambda v: {"timestamp":base.isoformat(),"interval":300,"items":v}
        payload = {
            "type":"long_sleep", "id":"private-health-record", "label":note,
            "bedtime_start":base.isoformat(),
            "bedtime_end":(base+timedelta(hours=hours)).isoformat(),
            "total_sleep_duration":hours*3600,
            "heart_rate":series(heart if isinstance(heart,list) else [heart]*count),
            "hrv":series(hrv if isinstance(hrv,list) else [hrv]*count),
        }
        with sqlite3.connect(self.db) as con:
            con.execute("INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)",
                        ("sleep",f"private-{lag}",day.isoformat(),
                         json.dumps(payload),"2026-11-01T00:00:00Z"))

    def test_prior7_medians_are_not_contaminated_by_selected_night(self):
        self.insert(0,heart=50,hrv=40)
        for lag in range(1,8):
            self.insert(lag,heart=50+lag,hrv=40+2*lag)
        result = comparison(self.db,self.end.isoformat())
        ctx = result["comparison"]
        self.assertTrue(ctx["previous_day"]["available"])
        self.assertEqual(ctx["previous_day"]["day"],"2026-10-30")
        self.assertEqual(ctx["previous_day"]["bins"][0]["heart_rate_bpm"],51)
        self.assertEqual(ctx["previous_7"]["nights_with_main_sleep"],7)
        self.assertEqual(ctx["previous_7"]["bins"][0]["heart_rate_bpm"],54)
        self.assertEqual(ctx["previous_7"]["bins"][0]["hrv_ms"],48)
        self.assertEqual(ctx["previous_7"]["bins"][0]["heart_rate_bpm_n"],7)
        self.assertEqual(ctx["deltas"]["heart_rate_bpm"]["previous_day"]["median_delta"],-1)
        self.assertEqual(ctx["deltas"]["heart_rate_bpm"]["previous_7"]["median_delta"],-4)
        self.assertEqual(ctx["deltas"]["hrv_ms"]["previous_7"]["median_delta"],-8)
        self.assertEqual(ctx["deltas"]["hrv_ms"]["previous_7"]["paired_bins"],16)
        assert "private-health-record" not in json.dumps(result)
        assert "secret" not in json.dumps(result)
        assert '"items"' not in json.dumps(result)

    def test_exact_previous_night_missing_stays_missing(self):
        self.insert(0)
        for lag in range(2,8):
            self.insert(lag,heart=60)
        result=comparison(self.db,self.end.isoformat())
        ctx=result["comparison"]
        self.assertFalse(ctx["previous_day"]["available"])
        self.assertIsNone(ctx["previous_day"]["bins"][0]["heart_rate_bpm"])
        self.assertIsNone(ctx["deltas"]["hrv_ms"]["previous_day"]["median_delta"])
        self.assertEqual(ctx["previous_7"]["nights_with_main_sleep"],6)
        self.assertEqual(ctx["previous_7"]["bins"][0]["heart_rate_bpm_n"],6)
        self.assertEqual(ctx["deltas"]["heart_rate_bpm"]["previous_7"]["median_delta"],-10)

    def test_incomplete_week_suppresses_profiles_not_zero_filling(self):
        self.insert(0,heart=50)
        for lag in (1,3,5):
            self.insert(lag,heart=65)
        ctx=comparison(self.db,self.end.isoformat())["comparison"]
        self.assertEqual(ctx["previous_7"]["nights_with_main_sleep"],3)
        self.assertIsNone(ctx["previous_7"]["bins"][0]["heart_rate_bpm"])
        self.assertEqual(ctx["previous_7"]["bins"][0]["heart_rate_bpm_n"],3)
        self.assertIsNone(ctx["deltas"]["heart_rate_bpm"]["previous_7"]["median_delta"])

    def test_compare_equal_elapsed_time_not_clock_time_and_shorter_night(self):
        self.insert(0)
        self.insert(1,hours=4,heart=60)
        for lag in range(2,8):
            self.insert(lag,hours=4,heart=70)
        ctx=comparison(self.db,self.end.isoformat())["comparison"]
        self.assertEqual(len(ctx["previous_7"]["bins"]),16)
        self.assertEqual(ctx["previous_7"]["bins"][0]["heart_rate_bpm"],70)
        self.assertIsNone(ctx["previous_7"]["bins"][8]["heart_rate_bpm"])
        self.assertIsNone(ctx["previous_day"]["bins"][8]["heart_rate_bpm"])
        self.assertEqual(ctx["previous_7"]["bins"][8]["heart_rate_bpm_n"],0)

    def test_selected_first_and_second_half_gated(self):
        self.insert(0,heart=[50]*48+[60]*48,hrv=[40]*48+[55]*48)
        result=comparison(self.db,self.end.isoformat())
        halves=result["comparison"]["selected_halves"]
        self.assertEqual(halves["heart_rate_bpm"]["first_half_median"],50)
        self.assertEqual(halves["heart_rate_bpm"]["second_half_median"],60)
        self.assertEqual(halves["heart_rate_bpm"]["second_minus_first"],10)
        self.assertEqual(halves["hrv_ms"]["second_minus_first"],15)
        self.assertTrue(halves["hrv_ms"]["sufficient"])
        self.insert(0,heart=[50]*12+[None]*84,hrv=[40]*12+[None]*84)
        halves=comparison(self.db,self.end.isoformat())["comparison"]["selected_halves"]
        self.assertIsNone(halves["heart_rate_bpm"]["second_minus_first"])
        self.assertFalse(halves["hrv_ms"]["sufficient"])

    def test_bad_older_night_does_not_break_selected_profile(self):
        self.insert(0)
        self.insert(1)
        d=(self.end-timedelta(days=1)).isoformat()
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE records SET payload = ? WHERE day = ?",(
                json.dumps({"type":"long_sleep","bedtime_start":"bad",
                            "bedtime_end":"bad","total_sleep_duration":29000}),d))
        ctx=comparison(self.db,self.end.isoformat())["comparison"]
        self.assertFalse(ctx["previous_day"]["available"])

    def test_minimum_window_and_variability_require_qualified_bins(self):
        # Each 30 minute bin contains six 5-minute samples.
        values=[60]*12+[52]*6+[55]*6+[57]*72
        hrv=[40]*24+[60]*72
        self.insert(0,heart=values,hrv=hrv)
        profile=comparison(self.db,self.end.isoformat())
        metrics=profile["comparison"]["intranight"]
        hr=metrics["heart_rate"]
        self.assertEqual(hr["minimum_bin_start_elapsed_minutes"],60)
        self.assertEqual(hr["minimum_bin_median_bpm"],52)
        self.assertEqual(hr["qualified_bins"],16)
        self.assertIsNotNone(hr["median_bin_range_p90_minus_p10_bpm"])
        self.assertIsNotNone(metrics["hrv"]["median_bin_range_p90_minus_p10_ms"])
        self.insert(0,heart=[50]*18+[None]*78,hrv=[40]*18+[None]*78)
        limited=comparison(self.db,self.end.isoformat())["comparison"]["intranight"]
        self.assertIsNone(limited["heart_rate"]["minimum_bin_start_elapsed_minutes"])
        self.assertIsNone(limited["heart_rate"]["median_bin_range_p90_minus_p10_bpm"])
        self.assertIsNone(limited["hrv"]["median_bin_range_p90_minus_p10_ms"])

    def test_no_selected_night_gives_none(self):
        self.insert(1)
        self.assertIsNone(comparison(self.db,self.end.isoformat()))


if __name__=="__main__":
    unittest.main()
