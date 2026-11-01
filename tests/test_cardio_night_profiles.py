"""Synthetic and privacy-first tests for M1 HR/HRV night profiles."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

import cardio_night_profiles as engine
import dashboard_server
import oura_self_analysis as oura


class NightProfilesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "data.sqlite3"
        self.day = date.today().isoformat()
        with sqlite3.connect(self.db) as db:
            db.execute("""CREATE TABLE records (
               collection TEXT, record_id TEXT, day TEXT, payload TEXT,
               synced_at TEXT, PRIMARY KEY(collection, record_id))""")

    def insert(self, item, day=None, key="main"):
        d = day or self.day
        with sqlite3.connect(self.db) as con:
            con.execute("INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?, ?)",
                        ("sleep", key, d, json.dumps(item), "2026-11-01T00:00:00Z"))

    def night(self, hr=None, hrv=None):
        start = "2026-10-31T23:00:00+01:00"
        end = "2026-11-01T07:00:00+01:00"
        return {"type": "long_sleep", "id": "secret-private-id",
                "bedtime_start": start, "bedtime_end": end,
                "total_sleep_duration": 7 * 3600,
                "heart_rate": hr, "hrv": hrv}

    @staticmethod
    def series(items, time="2026-10-31T23:00:00+01:00", interval=300):
        return {"timestamp": time, "interval": interval, "items": items}

    def test_binning_has_real_missing_gaps_and_independent_hrv(self):
        hr = self.series([50, 52, 54, 56, None, 60,
                          None, None, None, None, None, None,
                          63, 65, 67, 69, 71, 73])
        hrv = self.series([40, 42, 44, 46, 48, 50,
                           51, 53, 55, 57, 59, 61,
                           None, 70, 72, 74, 76, 78])
        result = engine.build_profile(self.night(hr, hrv), self.day)
        bins = result["bins"]
        self.assertEqual(bins[0]["heart_rate_bpm"], 54)
        self.assertIsNone(bins[1]["heart_rate_bpm"])
        self.assertEqual(bins[1]["hrv_ms"], 56)
        self.assertEqual(bins[2]["hrv_ms_n"], 5)
        self.assertEqual(bins[2]["heart_rate_bpm"], 68)
        self.assertEqual(len(bins), 16)
        self.assertTrue(all(b["heart_rate_bpm"] is None for b in bins[3:]))
        self.assertNotIn("secret-private-id", json.dumps(result))
        self.assertNotIn('"items"', json.dumps(result))
        self.assertNotIn("2026-10-31T23:00:00", json.dumps(result))
        self.assertEqual(result["bin_minutes"], 30)
        self.assertEqual(result["channels"]["heart_rate"]["valid_samples"], 11)
        self.assertEqual(result["channels"]["heart_rate"]["full_night_expected_samples"], 96)
        self.assertEqual(result["channels"]["heart_rate"]["full_night_coverage_fraction"], .115)

    def test_utc_alignment_shift_not_index(self):
        hr = self.series([50]*12, "2026-10-31T23:00:00+01:00")
        # HRV begins fifteen minutes later; must not pretend these arrays
        # are aligned by positional index.
        hrv = self.series([40]*12, "2026-10-31T22:15:00Z")
        result = engine.build_profile(self.night(hr, hrv), self.day)
        self.assertEqual(result["bins"][0]["heart_rate_bpm_n"], 6)
        self.assertEqual(result["bins"][0]["hrv_ms_n"], 3)
        self.assertIsNone(result["bins"][0]["hrv_ms"])
        self.assertEqual(result["bins"][1]["hrv_ms"], 40)
        self.assertEqual(result["bins"][2]["hrv_ms_n"], 3)

    def test_dst_repeated_local_hour_does_not_collapse_utc(self):
        session = self.night(
            self.series([54]*6, "2026-10-25T01:30:00+02:00"),
            self.series([44]*6, "2026-10-25T01:30:00+02:00"))
        session["bedtime_start"] = "2026-10-25T01:30:00+02:00"
        session["bedtime_end"] = "2026-10-25T03:30:00+01:00"
        result = engine.build_profile(session, "2026-10-25")
        self.assertEqual(result["duration_minutes"], 180)
        self.assertEqual(len(result["bins"]), 6)
        self.assertEqual(result["bins"][0]["elapsed_minutes"], 0)
        self.assertEqual(result["bins"][0]["hrv_ms"], 44)

    def test_invalid_interval_and_bad_values_have_no_fake_trace(self):
        hr = self.series([True, 9999, float("inf"), None, 40, 42], interval=150)
        session = self.night(hr, self.series([45]*7, interval=300))
        result = engine.build_profile(session,self.day)
        self.assertEqual(result["channels"]["heart_rate"]["status"], "nonstandard_interval")
        self.assertEqual(result["channels"]["heart_rate"]["invalid_samples"], 3)
        self.assertTrue(all(x["heart_rate_bpm"] is None for x in result["bins"]))
        self.assertEqual(result["channels"]["heart_rate"]["valid_samples"], 2)
        self.assertEqual(result["channels"]["hrv"]["qualified_bins"], 1)

    def test_long_sleep_only_avoids_nap_and_bounds(self):
        self.insert({"type":"rest","total_sleep_duration":100000,
                     "heart_rate":self.series([40]*12)},key="nap")
        self.insert(self.night(self.series([50]*12),self.series([40]*12)),key="main")
        profile=engine.night_profile(self.db,self.day)
        self.assertIsNotNone(profile)
        self.assertEqual(profile["bins"][0]["heart_rate_bpm"],50)
        self.assertEqual(profile["channels"]["hrv"]["qualified_bins"],2)
        with sqlite3.connect(self.db) as con:
            con.execute("DELETE FROM records WHERE record_id='main'")
        self.assertIsNone(engine.night_profile(self.db,self.day))
        with self.assertRaises(ValueError):
            engine.build_profile({"bedtime_start":"2026-10-31T23:00:00+01:00",
                                  "bedtime_end":"2026-10-30T08:00:00+01:00"},self.day)

    def test_endpoint_security_dates_and_minimization(self):
        self.insert(self.night(self.series([50]*12),
                               self.series([45]*12)))
        with patch.object(oura, "DB_PATH", self.db):
            server=dashboard_server.ThreadingHTTPServer(
                ("127.0.0.1",0),dashboard_server.DashboardHandler)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                def get(path,headers=None):
                    con=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
                    try:
                        con.request("GET",path,headers=headers or {})
                        response=con.getresponse()
                        return response.status,dict(response.getheaders()),response.read()
                    finally:
                        con.close()
                endpoint="/api/v2/recovery/night?day="+self.day
                status,headers,data=get(endpoint)
                self.assertEqual(status,200)
                payload=json.loads(data)
                self.assertEqual(payload["day"],self.day)
                self.assertEqual(len(payload["bins"]),16)
                self.assertEqual(headers["Cache-Control"],"no-store")
                self.assertNotIn("secret-private-id",data.decode())
                self.assertNotIn('"timestamp"',data.decode())
                for q in ("?day=2026-02-31","?day=2020-01-01",
                          "?day=../../data.sqlite3",
                          "?day="+self.day+"&day="+self.day,
                          "?day="+self.day+"&name=test",""):
                    self.assertEqual(get("/api/v2/recovery/night"+q)[0],400)
                self.assertEqual(get(endpoint,{"Host":"evil.example"})[0],403)
                yesterday=(date.today()-timedelta(days=1)).isoformat()
                self.assertEqual(get("/api/v2/recovery/night?day="+yesterday)[0],404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__=="__main__":
    unittest.main()
