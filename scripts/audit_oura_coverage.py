#!/usr/bin/env python3
"""Private, aggregate-only coverage audit for Oura SQLite.

No physiological readings, record IDs, times of day, tokens or raw payloads
are written to the report or printed. Counts remain on the Mac in 0600 files.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys

import oura_self_analysis as oura
from local_enrichment import EXPORT_FOLDER, write_atomically

NEEDED = {
    "sleep": ("total_sleep_duration", "average_hrv", "lowest_heart_rate",
              "average_breath", "bedtime_start", "bedtime_end", "latency"),
    "daily_sleep": ("score",),
    "daily_readiness": ("score",),
    "daily_activity": ("score", "steps"),
    "workout": ("activity", "start_datetime", "end_datetime", "intensity"),
}


def audit(db: Path, *, days: int = 65, today: date | None = None) -> dict:
    if not 35 <= days <= 90:
        raise ValueError("Coverage audit window must be 35–90 days.")
    if not db.is_file():
        raise oura.OuraError("No local Oura database.")
    today = today or date.today()
    start = today - timedelta(days=days-1)
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    aggregates = {key: {
        "record_count": 0, "days": set(), "fields": Counter(), "invalid_json": 0
    } for key in NEEDED}
    try:
        rows = connection.execute(
            "SELECT collection, day, payload FROM records "
            "WHERE day BETWEEN ? AND ?",
            (start.isoformat(), today.isoformat()))
        for collection, day, raw in rows:
            if collection not in aggregates:
                continue
            item = aggregates[collection]
            item["record_count"] += 1
            try:
                body = json.loads(raw)
            except (ValueError, TypeError):
                item["invalid_json"] += 1
                continue
            if not isinstance(body, dict):
                item["invalid_json"] += 1
                continue
            if collection == "sleep" and body.get("type") not in ("long_sleep", None):
                # Do not mix nap records with the main overnight measurements.
                continue
            item["days"].add(day)
            for field in NEEDED[collection]:
                if body.get(field) is not None:
                    item["fields"][field] += 1
    finally:
        connection.close()
    summary = {}
    for collection, group in aggregates.items():
        counts = group["fields"]
        observed = len(group["days"])
        summary[collection] = {
            "records_seen": group["record_count"],
            "observed_calendar_days": observed,
            "coverage_pct": round(observed / days * 100, 1),
            "field_non_null_counts": {field: counts[field] for field in NEEDED[collection]},
            "invalid_json_records": group["invalid_json"],
        }
    sleep = summary["sleep"]
    usable_main_sleep = min(sleep["field_non_null_counts"]["average_hrv"],
                            sleep["field_non_null_counts"]["lowest_heart_rate"])
    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "window": {"days": days, "start": start.isoformat(), "end": today.isoformat()},
        "collections": summary,
        "readiness": {
            "recent_7_and_prior_28_possible_from_total_sleep_count":
                usable_main_sleep >= 35,
            "minimum_eligible_hrv_records_observed": usable_main_sleep,
            "workout_records_observed": summary["workout"]["record_count"],
        },
        "privacy": "Aggregate coverage only; private local report, not for GitHub artifacts.",
        "limitations": [
            "A sufficient total record count does not guarantee coverage of both disjoint windows.",
            "Workouts not recorded in Oura are invisible; zero records does not imply rest.",
            "Counts measure field presence, not signal validity or clinical quality.",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Private Oura field coverage audit")
    parser.add_argument("--days", type=int, default=65)
    parser.add_argument("--out", type=Path, default=EXPORT_FOLDER / "coverage_audit.json")
    args = parser.parse_args(argv)
    try:
        report = audit(oura.DB_PATH, days=args.days)
        write_atomically(args.out,
                         lambda f: json.dump(report, f, ensure_ascii=False, indent=2))
        print("Copertura verificata. Report locale riservato: " + str(args.out))
        return 0
    except (oura.OuraError, ValueError, sqlite3.Error, OSError) as exc:
        print("Audit non completato: " + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
