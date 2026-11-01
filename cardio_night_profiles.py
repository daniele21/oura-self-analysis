"""Local Oura sleep HR/HRV profiles: strictly bounded and deterministic.

Only read a selected night, never sync new data. PublicSample timestamps are
absolute offsets; sample instants use timestamp + index * interval in UTC.
No interpolation of missing values. Return only half-hour median bins and
coverage, not raw timestamped measurements or identifying record IDs.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sqlite3
from statistics import median

MAX_NIGHT_RECORDS = 16
MAX_JSON_BYTES = 350_000
MAX_SAMPLES = 600
MAX_DURATION_MINUTES = 24 * 60
BIN_MINUTES = 30
MIN_POINTS_PER_BIN = 4
METRICS = {"heart_rate": (25.0, 220.0), "hrv": (1.0, 300.0)}


class NightProfileError(ValueError):
    pass


def aware(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 80:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def valid_number(value: object, limits: tuple[float, float]) -> float | None:
    if (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and limits[0] <= value <= limits[1]):
        return float(value)
    return None


def choose_session(records: list[dict]) -> dict | None:
    eligible = [r for r in records if r.get("type") == "long_sleep"]
    return max(eligible, key=lambda r: valid_number(
        r.get("total_sleep_duration"), (0, 86400)) or 0) if eligible else None


def read_main_sleep(db: Path, day: str) -> dict | None:
    if not db.is_file():
        raise FileNotFoundError("Local Oura database not found.")
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        values = connection.execute(
            "SELECT payload FROM records WHERE collection = 'sleep' AND day = ? "
            "LIMIT ?", (day, MAX_NIGHT_RECORDS + 1)
        ).fetchall()
    finally:
        connection.close()
    if len(values) > MAX_NIGHT_RECORDS:
        raise NightProfileError("Too many sleep sessions on selected day.")
    records = []
    for (raw,) in values:
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_JSON_BYTES:
            raise NightProfileError("Sleep record exceeds processing bound.")
        try:
            record = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return choose_session(records)


def sample_offsets(sample: object, bedtime: datetime, wake: datetime,
                   field: str) -> tuple[dict[int, float | None], dict]:
    """Return (absolute UTC second -> sample, meta). No timezone flattening."""
    out: dict[int, float | None] = {}
    summary = {"available": False, "sample_interval_seconds": None,
               "expected_samples": 0, "valid_samples": 0,
               "missing_samples": 0, "invalid_samples": 0,
               "duplicates": 0, "out_of_bed_window": 0,
               "status": "missing"}
    if sample is None:
        return out, summary
    if not isinstance(sample, dict):
        summary["status"] = "invalid_format"
        return out, summary
    start = aware(sample.get("timestamp"))
    interval = sample.get("interval")
    values = sample.get("items")
    if (start is None or not isinstance(interval, (int, float)) or
            isinstance(interval, bool) or not math.isfinite(interval) or
            not (60 <= interval <= 1800) or
            not isinstance(values, list) or len(values) > MAX_SAMPLES):
        summary["status"] = "invalid_format"
        return out, summary
    summary["available"] = True
    summary["status"] = "ok" if abs(interval - 300) < 1e-9 else "nonstandard_interval"
    summary["sample_interval_seconds"] = interval
    start_utc = start.astimezone(timezone.utc)
    begin_utc = bedtime.astimezone(timezone.utc)
    end_utc = wake.astimezone(timezone.utc)
    low, high = METRICS[field]
    for i, value in enumerate(values):
        instant = start_utc + timedelta(seconds=i * interval)
        # use actual UTC timestamps, not wall-time indices; DST safe.
        if not begin_utc <= instant < end_utc:
            summary["out_of_bed_window"] += 1
            continue
        tick = int(round(instant.timestamp()))
        if tick in out:
            summary["duplicates"] += 1
            # A repeated timestamp must not be counted twice or overwritten.
            continue
        number = valid_number(value, (low, high))
        out[tick] = number
        if value is None:
            summary["missing_samples"] += 1
        elif number is None:
            summary["invalid_samples"] += 1
        else:
            summary["valid_samples"] += 1
    summary["expected_samples"] = len(out)
    return out, summary


def build_profile(session: dict, day: str) -> dict:
    start = aware(session.get("bedtime_start"))
    end = aware(session.get("bedtime_end"))
    if start is None or end is None:
        raise NightProfileError("Main sleep requires timezone-aware bedtime and wake.")
    length = (end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds()
    if not 0 < length <= MAX_DURATION_MINUTES * 60:
        raise NightProfileError("Invalid main sleep duration.")
    slots = min(48, math.ceil(length / (BIN_MINUTES * 60)))
    data = {}
    meta = {}
    for field in METRICS:
        data[field], meta[field] = sample_offsets(session.get(field), start, end, field)
    start_utc = start.astimezone(timezone.utc)
    # Always create complete bins for every elapsed half-hour; nulls stay null.
    bins = []
    for i in range(slots):
        low = start_utc + timedelta(minutes=i * BIN_MINUTES)
        high = min(start_utc + timedelta(minutes=(i + 1)* BIN_MINUTES),
                   end.astimezone(timezone.utc))
        row = {"elapsed_minutes": i * BIN_MINUTES}
        for field, label in (("heart_rate", "heart_rate_bpm"), ("hrv", "hrv_ms")):
            readings = [v for timestamp, v in data[field].items()
                        if low.timestamp() <= timestamp < high.timestamp() and v is not None]
            row[label + "_n"] = len(readings)
            # Do not connect gaps or fill low-quality bins with invented values.
            row[label] = round(median(readings), 2) if (
                meta[field]["status"] == "ok" and len(readings) >= MIN_POINTS_PER_BIN
            ) else None
        bins.append(row)
    for field, label in (("heart_rate", "heart_rate_bpm"), ("hrv", "hrv_ms")):
        quality = meta[field]
        quality["qualified_bins"] = sum(b[label] is not None for b in bins)
        quality["total_bins"] = slots
        quality["valid_sample_fraction"] = round(
            quality["valid_samples"] / quality["expected_samples"], 3
        ) if quality["expected_samples"] else None
        quality["usable"] = quality["qualified_bins"] >= 2
    return {
        "version": "1.0",
        "day": day,
        "bedtime_clock": start.strftime("%H:%M"),
        "wake_clock": end.strftime("%H:%M"),
        "duration_minutes": round(length/60, 1),
        "bin_minutes": BIN_MINUTES,
        "min_valid_samples_per_bin": MIN_POINTS_PER_BIN,
        "channels": meta,
        "bins": bins,
        "method": "30-min median bins from independently timestamped Oura sleep PublicSample arrays",
        "limitations": [
            "30-minute groups are a descriptive engineering aggregation, not a validated clinical estimator.",
            "Only groups with 4+ valid five-minute samples are shown; missing groups are blank.",
            "The horizontal axis is elapsed time from bedtime, not timezone-sensitive local clock.",
            "Overnight wearable HRV/HR measurements do not diagnose stress, illness, or recovery.",
            "Oura summary-level lowest HR and average HRV can use different aggregations.",
        ],
    }


def night_profile(db: Path, day: str) -> dict | None:
    """None means no main night. Fail gracefully only for malformed series fields."""
    date.fromisoformat(day)  # query layer validates tighter bounds
    session = read_main_sleep(db, day)
    if session is None:
        return None
    return build_profile(session, day)
