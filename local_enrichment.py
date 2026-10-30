#!/usr/bin/env python3
"""Local deterministic Oura enrichment; optional export to a Drive desktop folder.

No Oura or Google credentials leave the Mac. No external AI is used.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict
from statistics import mean

import oura_self_analysis as oura

SCHEMA_VERSION = "1.0"
EXPORT_FOLDER = oura.APP_HOME / "enriched"
CSV_NAME = "daily_enriched.csv"
MANIFEST_NAME = "manifest.json"
FIELDS = [
    "day", "sleep_score", "readiness_score", "activity_score", "steps",
    "total_sleep_minutes", "deep_sleep_minutes", "rem_sleep_minutes",
    "light_sleep_minutes", "awake_minutes", "sleep_efficiency_pct",
    "lowest_heart_rate_bpm", "average_heart_rate_bpm", "average_hrv_ms",
    "temperature_deviation_c", "spo2_average_pct",
    "sleep_score_avg7", "readiness_score_avg7", "hrv_avg7",
    "total_sleep_minutes_avg7",
    "sleep_score_vs_prev28", "readiness_score_vs_prev28", "hrv_vs_prev28",
    "missing_sources",
]


def number(value):
    """Preserve missing (None) rather than converting it to zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    from math import isfinite
    return float(value) if isfinite(value) else None


def rnd(value, places=1):
    return round(value, places) if value is not None else None


def minutes(value):
    value = number(value)
    return rnd(value / 60) if value is not None else None


def nested_number(source: dict, *keys: str):
    current = source
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return number(current)


def choose_sleep(records: list[dict]) -> dict:
    """Prefer main overnight sleep over naps; select longest of same type."""
    if not records:
        return {}
    candidates = [r for r in records if r.get("type") == "long_sleep"]
    if not candidates:
        candidates = [r for r in records if r.get("type") != "rest"]
    if not candidates:
        return {}
    return max(candidates, key=lambda r: number(r.get("total_sleep_duration")) or 0)


def daily_records(db: Path, start: date, end: date) -> dict[str, dict[str, list[dict]]]:
    if not db.is_file():
        raise oura.OuraError("No local SQLite records. Run the Oura sync first.")
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT day, collection, payload FROM records WHERE day BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        )
        for day, collection, payload in rows:
            if not day:
                continue
            try:
                item = json.loads(payload)
            except (ValueError, TypeError) as exc:
                raise oura.OuraError("Invalid locally stored record JSON.") from exc
            if isinstance(item, dict):
                grouped[day][collection].append(item)
    finally:
        con.close()
    return grouped


def first(records: list[dict]) -> dict:
    return records[0] if records else {}


def make_base(day: str, records: dict[str, list[dict]]) -> dict:
    daily_sleep = first(records.get("daily_sleep", []))
    daily_readiness = first(records.get("daily_readiness", []))
    daily_activity = first(records.get("daily_activity", []))
    detailed_sleep = choose_sleep(records.get("sleep", []))
    spo2 = first(records.get("daily_spo2", []))
    missing = [
        name for name in ("daily_sleep", "sleep", "daily_readiness", "daily_activity")
        if not records.get(name)
    ]
    return {
        "day": day,
        "sleep_score": number(daily_sleep.get("score")),
        "readiness_score": number(daily_readiness.get("score")),
        "activity_score": number(daily_activity.get("score")),
        "steps": number(daily_activity.get("steps")),
        "total_sleep_minutes": minutes(detailed_sleep.get("total_sleep_duration")),
        "deep_sleep_minutes": minutes(detailed_sleep.get("deep_sleep_duration")),
        "rem_sleep_minutes": minutes(detailed_sleep.get("rem_sleep_duration")),
        "light_sleep_minutes": minutes(detailed_sleep.get("light_sleep_duration")),
        "awake_minutes": minutes(detailed_sleep.get("awake_time")),
        "sleep_efficiency_pct": number(detailed_sleep.get("efficiency")),
        "lowest_heart_rate_bpm": number(detailed_sleep.get("lowest_heart_rate")),
        "average_heart_rate_bpm": number(detailed_sleep.get("average_heart_rate")),
        "average_hrv_ms": number(detailed_sleep.get("average_hrv")),
        "temperature_deviation_c": number(daily_readiness.get("temperature_deviation")),
        "spo2_average_pct": nested_number(spo2, "spo2_percentage", "average"),
        "missing_sources": ",".join(missing),
    }


def window_average(rows: dict[str, dict], current: date, field: str,
                   previous_days: int, include_today: bool, minimum: int) -> float | None:
    oldest = current - timedelta(days=previous_days - 1 if include_today else previous_days)
    newest = current if include_today else current - timedelta(days=1)
    values = [
        number(rows.get((oldest + timedelta(days=i)).isoformat(), {}).get(field))
        for i in range((newest - oldest).days + 1)
    ]
    clean = [v for v in values if v is not None]
    return mean(clean) if len(clean) >= minimum else None


def enrich_window(db: Path, days: int = 30, *, today: date | None = None) -> list[dict]:
    if not 1 <= days <= 90:
        raise oura.OuraError("Export window must be between 1 and 90 days.")
    today = today or date.today()
    start = today - timedelta(days=days - 1)
    # Read 28 prior days for baselines; export only the requested window.
    source = daily_records(db, start - timedelta(days=28), today)
    base = {day: make_base(day, collections) for day, collections in source.items()}
    # Only days with meaningful Oura content should produce rows.
    meaningful = ("sleep_score", "readiness_score", "activity_score",
                  "steps", "total_sleep_minutes", "average_hrv_ms", "spo2_average_pct")
    output = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        day = d.isoformat()
        row = base.get(day)
        if not row or all(row.get(k) is None for k in meaningful):
            continue
        row = row.copy()
        for source_field, prefix in (
            ("sleep_score", "sleep_score"),
            ("readiness_score", "readiness_score"),
            ("average_hrv_ms", "hrv"),
            ("total_sleep_minutes", "total_sleep_minutes"),
        ):
            row[prefix + "_avg7"] = rnd(window_average(
                base, d, source_field, previous_days=7, include_today=True, minimum=3))
        for source_field, prefix in (
            ("sleep_score", "sleep_score"),
            ("readiness_score", "readiness_score"),
            ("average_hrv_ms", "hrv"),
        ):
            baseline = window_average(
                base, d, source_field, previous_days=28, include_today=False, minimum=7)
            current = row.get(source_field)
            row[prefix + "_vs_prev28"] = rnd(current - baseline) if current is not None and baseline is not None else None
        output.append(row)
    if not output:
        raise oura.OuraError("No Oura data in this date window; refusing to publish an empty export.")
    return output


def write_atomically(path: Path, writer) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".oura-tmp-", dir=path.parent)
    try:
        os.chmod(temp, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def export_local(db: Path, days: int = 30, *, today: date | None = None,
                 export_folder: Path | None = None) -> tuple[Path, Path, dict]:
    export_folder = export_folder or EXPORT_FOLDER
    data = enrich_window(db, days=days, today=today)
    csv_path = export_folder / CSV_NAME
    manifest_path = export_folder / MANIFEST_NAME

    def write_csv(stream):
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow({k: "" if row.get(k) is None else row[k] for k in FIELDS})

    write_atomically(csv_path, write_csv)
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "day_from": data[0]["day"],
        "day_to": data[-1]["day"],
        "row_count": len(data),
        "window_days": days,
        "csv_sha256": digest,
        "filename": CSV_NAME,
        "source": "Local Oura SQLite; enrichment uses deterministic rules, not AI",
        "notes": "Missing values are blank; 7-day means need >=3 records; 28-day baseline needs >=7 previous days. No medical conclusions.",
    }
    write_atomically(manifest_path, lambda f: json.dump(manifest, f, ensure_ascii=False, indent=2))
    return csv_path, manifest_path, manifest


def publish_to_drive(csv_path: Path, manifest_path: Path, folder: Path) -> None:
    """Publish into an explicitly selected Google Drive Desktop synced folder.

    An atomic rename reduces partially-written files. Drive Desktop then handles
    Google authentication and cloud sync outside this program.
    """
    folder = folder.expanduser()
    if folder.is_symlink():
        raise oura.OuraError("Refusing a symlinked Drive destination.")
    folder = folder.resolve()
    if not folder.is_dir():
        raise oura.OuraError(f"Drive destination does not exist: {folder}")
    # Caller must explicitly select a folder within their *private* Drive.
    # We do not assume any arbitrary local directory is backed up automatically.
    for source in (csv_path, manifest_path):
        destination = folder / source.name
        if destination.is_symlink():
            raise oura.OuraError("Refusing to overwrite a symlink in Drive.")
        fd, temp = tempfile.mkstemp(prefix=".oura-upload-", dir=folder)
        try:
            with os.fdopen(fd, "wb") as out, open(source, "rb") as inp:
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, destination)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enrich Oura records on Mac and optionally publish to a private Drive Desktop folder")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("enrich", "publish", "run"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--days", type=int, default=30,
                         help="Rolling export window (1-90 days, default 30)")
        if command != "enrich":
            cmd.add_argument("--drive-dir", type=Path, required=True,
                             help="Existing private Google Drive for Desktop synced folder")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            from argparse import Namespace
            # Fail closed: don't upload a snapshot after a failed API sync.
            oura.sync(Namespace(days=args.days, start=None, end=None,
                                collections=",".join(oura.DEFAULT_COLLECTIONS)))
        csv_path, manifest_path, meta = export_local(oura.DB_PATH, days=args.days)
        print(f"Local enrichment: {meta['row_count']} days -> {csv_path}")
        if args.command in ("publish", "run"):
            publish_to_drive(csv_path, manifest_path, args.drive_dir)
            print(f"Copied 2 files to Drive Desktop folder: {args.drive_dir.expanduser()}")
            print("Cloud synchronization is handled by Google Drive for Desktop; verify its sync status.")
        return 0
    except (oura.OuraError, sqlite3.Error, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
