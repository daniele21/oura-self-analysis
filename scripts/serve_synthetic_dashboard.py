#!/usr/bin/env python3
"""Synthetic-only local server for visual regression tests.

Never opens the user's Oura DB. Uses a temporary SQLite file with explicitly
fictional dates, measures and ids, then serves on 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
import json
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dashboard_server
import oura_self_analysis as oura


def fixture(path: Path, scenario: str):
    today = date.today()
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE records (
            collection TEXT NOT NULL, record_id TEXT NOT NULL, day TEXT NOT NULL,
            payload TEXT NOT NULL, synced_at TEXT NOT NULL,
            PRIMARY KEY(collection,record_id)
        )""")
        for n in range(96):
            day = today - timedelta(days=n)
            if scenario == "empty" or scenario == "sparse" and n % 6 != 0:
                continue
            if n in (3, 11, 22, 36, 61):
                continue  # missing nights are not zeros
            baseline = 6 if n % 7 in (0, 1) else 0
            total_minutes = 429 + baseline + (n % 5) * 3
            deep_minutes = 83 + n % 9 * 3
            rem_minutes = 91 + (n % 6) * 4
            light_minutes = total_minutes - deep_minutes - rem_minutes
            start = datetime(day.year, day.month, day.day, 23, 30, tzinfo=timezone.utc)-timedelta(days=1)
            payload = {
                "type":"long_sleep", "id":"SYNTHETIC-ONLY",
                "bedtime_start":start.isoformat(),
                "bedtime_end":(start+timedelta(hours=8)).isoformat(),
                "total_sleep_duration":total_minutes*60,
                "light_sleep_duration":light_minutes*60,
                "deep_sleep_duration":deep_minutes*60,
                "rem_sleep_duration":rem_minutes*60,
                "efficiency":90,
                "lowest_heart_rate":53+n%7,
                "average_hrv":52+n%13,
                "average_heart_rate":60+n%6,
                "latency":780,
                "awake_time":(8*60-total_minutes)*60,
            }
            db.execute("INSERT INTO records VALUES(?,?,?,?,?)",
                ("sleep",f"synthetic-sleep-{n}",day.isoformat(),
                 json.dumps(payload),today.isoformat()+"T12:00:00Z"))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8766)
    parser.add_argument("--scenario",choices=("complete","sparse","empty"),default="complete")
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="oura-visual-SYNTHETIC-") as tmp:
        db=Path(tmp)/"synthetic.sqlite3"
        fixture(db,args.scenario)
        oura.DB_PATH=db
        dashboard_server.serve(args.port)


if __name__=="__main__":
    main()
