import csv
from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import local_enrichment as enrich
import oura_self_analysis as oura


class TestLocalEnrichment(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.db = self.path / "records.sqlite"
        con = sqlite3.connect(self.db)
        con.execute("""CREATE TABLE records (
            collection TEXT NOT NULL, record_id TEXT NOT NULL, day TEXT,
            payload TEXT NOT NULL, synced_at TEXT NOT NULL,
            PRIMARY KEY (collection, record_id)
        )""")
        con.commit()
        con.close()

    def add(self, kind, day, **attributes):
        row = {"id": kind + day, "day": day, **attributes}
        with sqlite3.connect(self.db) as con:
            con.execute("INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?, ?)",
                        (kind, row["id"], day, json.dumps(row), "2026-10-30T00:00:00Z"))

    def test_sleep_episode_preference_and_missing_data(self):
        day = "2026-10-30"
        self.add("daily_sleep", day, score=87)
        self.add("daily_readiness", day, score=71, temperature_deviation=0.1)
        self.add("daily_activity", day, score=91, steps=12345)
        self.add("sleep", day, type="long_sleep", total_sleep_duration=25200,
                 deep_sleep_duration=5400, rem_sleep_duration=6300,
                 light_sleep_duration=13500, average_hrv=44,
                 lowest_heart_rate=48, efficiency=92)
        self.add("daily_spo2", day, spo2_percentage={"average": 97.1})
        # A nap record on the same day must not overwrite the main sleep.
        with sqlite3.connect(self.db) as con:
            con.execute("INSERT INTO records VALUES (?, ?, ?, ?, ?)",
                        ("sleep", "nap-1", day,
                         json.dumps({"type":"rest", "total_sleep_duration": 3600}),
                         "2026-10-30T00:00:00Z"))
        rows = enrich.enrich_window(self.db, 3, today=date(2026, 10, 30))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["total_sleep_minutes"], 420)
        self.assertEqual(row["deep_sleep_minutes"], 90)
        self.assertEqual(row["average_hrv_ms"], 44)
        self.assertEqual(row["spo2_average_pct"], 97.1)
        self.assertEqual(row["steps"], 12345)
        self.assertEqual(row["missing_sources"], "")
        self.assertIsNone(row["sleep_score_vs_prev28"])

    def test_previous_28_day_baseline_excludes_today(self):
        current = date(2026, 10, 30)
        for back in (28, 27, 20, 14, 10, 5, 1):
            self.add("daily_sleep", (current - timedelta(days=back)).isoformat(), score=80)
        self.add("daily_sleep", current.isoformat(), score=90)
        row = enrich.enrich_window(self.db, 1, today=current)[0]
        self.assertEqual(row["sleep_score_vs_prev28"], 10)
        self.assertEqual(row["sleep_score_avg7"], 83.3)

    def test_missing_days_not_filled_with_zeros(self):
        self.add("daily_activity", "2026-10-28", steps=100, score=63)
        self.add("daily_activity", "2026-10-30", steps=0, score=72)
        rows = enrich.enrich_window(self.db, 3, today=date(2026, 10, 30))
        self.assertEqual([r["day"] for r in rows], ["2026-10-28", "2026-10-30"])
        self.assertEqual([r["steps"] for r in rows], [100, 0])
        self.assertIsNone(rows[1]["sleep_score"])
        self.assertIn("daily_sleep", rows[1]["missing_sources"])

    def test_export_is_idempotent_and_reflects_corrections(self):
        self.add("daily_sleep", "2026-10-30", score=82)
        folder = self.path / "output"
        csv_path, manifest_path, m1 = enrich.export_local(
            self.db, 1, today=date(2026, 10, 30), export_folder=folder)
        with open(csv_path, newline="", encoding="utf-8") as f:
            self.assertEqual(list(csv.DictReader(f))[0]["sleep_score"], "82.0")
        self.add("daily_sleep", "2026-10-30", score=85)
        _, _, m2 = enrich.export_local(
            self.db, 1, today=date(2026, 10, 30), export_folder=folder)
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sleep_score"], "85.0")
        self.assertNotEqual(m1["csv_sha256"], m2["csv_sha256"])
        self.assertEqual(json.loads(manifest_path.read_text())["csv_sha256"], m2["csv_sha256"])
        self.assertEqual(csv_path.stat().st_mode & 0o777, 0o600)

    def test_publish_to_existing_folder(self):
        self.add("daily_sleep", "2026-10-30", score=75)
        csv_path, manifest_path, _ = enrich.export_local(
            self.db, 1, today=date(2026, 10, 30), export_folder=self.path / "local")
        drive = self.path / "My Drive" / "Oura Self Analysis"
        drive.mkdir(parents=True)
        enrich.publish_to_drive(csv_path, manifest_path, drive)
        self.assertEqual((drive / enrich.CSV_NAME).read_bytes(), csv_path.read_bytes())
        self.assertEqual((drive / enrich.MANIFEST_NAME).read_bytes(), manifest_path.read_bytes())
        self.assertEqual(sorted(p.name for p in drive.iterdir()),
                         [enrich.CSV_NAME, enrich.MANIFEST_NAME])

    def test_refuse_missing_drive_folder(self):
        self.add("daily_sleep", "2026-10-30", score=75)
        csv_path, manifest_path, _ = enrich.export_local(
            self.db, 1, today=date(2026, 10, 30), export_folder=self.path / "local")
        with self.assertRaises(oura.OuraError):
            enrich.publish_to_drive(csv_path, manifest_path, self.path / "missing")

    def test_no_data_refuses_export(self):
        with self.assertRaises(oura.OuraError):
            enrich.export_local(self.db, 30, today=date(2026, 10, 30),
                                export_folder=self.path / "local")

    def test_export_window_limit(self):
        with self.assertRaises(oura.OuraError):
            enrich.enrich_window(self.db, 100, today=date(2026, 10, 30))

    def test_sync_failure_does_not_upload_stale_data(self):
        with patch.object(oura, "sync", side_effect=oura.OuraError("API failed")), \
             patch.object(enrich, "publish_to_drive") as publish:
            ret = enrich.main(["run", "--days", "30",
                               "--drive-dir", str(self.path)])
        self.assertEqual(ret, 1)
        publish.assert_not_called()

    def test_daily_run_fetches_7_days_but_exports_30(self):
        csv_path = self.path / "daily_enriched.csv"
        manifest_path = self.path / "manifest.json"
        with patch.object(oura, "sync") as sync, \
             patch.object(enrich, "export_local", return_value=(
                 csv_path, manifest_path, {"row_count": 3})) as export, \
             patch.object(enrich, "publish_to_drive") as publish:
            ret = enrich.main(["run", "--days", "30",
                               "--drive-dir", str(self.path)])
        self.assertEqual(ret, 0)
        self.assertEqual(sync.call_args.args[0].days, 7)
        self.assertEqual(export.call_args.kwargs["days"], 30)
        publish.assert_called_once()

    def test_daily_refresh_window_must_be_valid(self):
        with patch.object(oura, "sync") as sync:
            ret = enrich.main(["run", "--sync-days", "0",
                               "--drive-dir", str(self.path)])
        self.assertEqual(ret, 1)
        sync.assert_not_called()


if __name__ == "__main__":
    unittest.main()
