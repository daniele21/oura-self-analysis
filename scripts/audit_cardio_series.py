#!/usr/bin/env python3
"""Private aggregate-only audit for Oura V2 sleep HR/HRV PublicSample series.

Never emits individual measurements, timestamps, night IDs, or raw payloads.
Reads existing Oura SQLite in read-only mode. No network calls or new scopes.
The report stays in the Mac's application support directory (0600).
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

# Direct execution from scripts/ must also resolve the project root.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oura_self_analysis as oura

REPORT_DIR = Path.home() / "Library" / "Application Support" / "OuraSelfAnalysis" / "private-audits"
CHANNELS = ("heart_rate", "hrv")
MAX_WINDOW_DAYS = 90
MAX_RECORDS = 1000
MAX_ITEMS = 2000


def _bucket_interval(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return "invalid"
    if value <= 0:
        return "invalid"
    if abs(value-300) < .001:
        return "300s"
    if 0 < value < 300:
        return "shorter_than_300s"
    return "longer_than_300s"


def audit(db: Path, *, days: int = 65, today: date | None = None) -> dict:
    if not 7 <= days <= MAX_WINDOW_DAYS:
        raise ValueError("Days must be between 7 and 90.")
    if not db.is_file():
        raise FileNotFoundError("Local Oura SQLite is not available.")
    today = today or date.today()
    since = today - timedelta(days=days - 1)
    rows = 0
    valid_main = 0
    invalid_json = 0
    summary = {
        name: {
            "present_nights": 0, "missing_nights": 0,
            "schema_valid_nights": 0, "schema_invalid_nights": 0,
            "null_samples": 0, "valid_samples": 0, "invalid_samples": 0,
            "interval_class_counts": Counter(),
            "sample_count_bucket": Counter(),
            "coverage_bucket": Counter(),
        } for name in CHANNELS
    }
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cursor = connection.execute(
            "SELECT payload FROM records WHERE collection='sleep' "
            "AND day BETWEEN ? AND ? LIMIT ?",
            (since.isoformat(), today.isoformat(), MAX_RECORDS + 1),
        )
        for (raw,) in cursor:
            rows += 1
            if rows > MAX_RECORDS:
                raise ValueError("Too many sleep records for bounded audit.")
            try:
                item = json.loads(raw)
            except (ValueError, TypeError):
                invalid_json += 1
                continue
            if not isinstance(item, dict):
                invalid_json += 1
                continue
            if item.get("type") != "long_sleep":
                continue
            valid_main += 1
            for field in CHANNELS:
                stats = summary[field]
                sample = item.get(field)
                if sample is None:
                    stats["missing_nights"] += 1
                    continue
                stats["present_nights"] += 1
                if not isinstance(sample, dict):
                    stats["schema_invalid_nights"] += 1
                    continue
                interval = sample.get("interval")
                values = sample.get("items")
                timestamp = sample.get("timestamp")
                interval_class = _bucket_interval(interval)
                stats["interval_class_counts"][interval_class] += 1
                if (not isinstance(values, list) or len(values) > MAX_ITEMS or
                        interval_class == "invalid" or
                        not isinstance(timestamp, str) or
                        len(timestamp) > 80):
                    stats["schema_invalid_nights"] += 1
                    continue
                # Never persist the timestamp. Only check it is parseable and aware.
                from datetime import datetime
                try:
                    time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    time = None
                if time is None or time.utcoffset() is None:
                    stats["schema_invalid_nights"] += 1
                    continue
                stats["schema_valid_nights"] += 1
                n_valid = n_null = n_invalid = 0
                for v in values:
                    if v is None:
                        n_null += 1
                    elif isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and (
                        25 <= v <= 220 if field == "heart_rate" else 1 <= v <= 300
                    ):
                        n_valid += 1
                    else:
                        n_invalid += 1
                stats["valid_samples"] += n_valid
                stats["null_samples"] += n_null
                stats["invalid_samples"] += n_invalid
                share = n_valid / len(values) if values else 0
                band = "75-100%" if share >= .75 else "50-74%" if share >= .5 else "1-49%" if share > 0 else "0%"
                stats["coverage_bucket"][band] += 1
                count = len(values)
                size_band = "0" if count == 0 else "1-48" if count <= 48 else "49-144" if count <= 144 else "145+"
                stats["sample_count_bucket"][size_band] += 1
    finally:
        connection.close()
    return {
        "schema_version": "1.0",
        "audit_window_days": days,
        "sleep_records_checked": rows,
        "long_sleep_sessions_checked": valid_main,
        "invalid_json_records": invalid_json,
        "channels": {
            field: {key: dict(value) if isinstance(value, Counter) else value
                    for key, value in summary[field].items()}
            for field in CHANNELS
        },
        "privacy": "Private aggregate metadata only; no sample values, timestamps or IDs.",
        "limitations": [
            "The report counts main sleep sessions, not distinct days.",
            "It is possible for a field to exist but contain no useful samples.",
            "Coverage fractions describe Oura exported samples, not ECG validation.",
        ],
    }


def _write_private(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    handle, temporary = tempfile.mkstemp(prefix=".oura-audit-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit local Oura HR/HRV series structure without disclosing readings")
    parser.add_argument("--days", type=int, default=65)
    parser.add_argument("--out", type=Path, default=REPORT_DIR / "cardio-series-coverage.json")
    args = parser.parse_args(argv)
    try:
        result = audit(oura.DB_PATH, days=args.days)
        _write_private(args.out, result)
        # Only categorical readiness, never counts / dates / sample values in CI logs.
        ready = all(result["channels"][name]["schema_valid_nights"] > 0 for name in CHANNELS)
        print("Cardio series audit: " + ("both_channels_present" if ready else "missing_or_invalid_channels"))
        print("Private audit saved locally; physiological values were not printed.")
        return 0
    except (OSError, sqlite3.Error, ValueError) as exc:
        print("Cardio series audit failed: " + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
