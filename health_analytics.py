#!/usr/bin/env python3
"""Evidence-informed, deterministic health analytics for local Oura SQLite.

These are descriptive, non-clinical metrics. No AI models and no network calls.
Values are never treated as diagnoses, medical alerts or training prescriptions.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from statistics import mean, median, pstdev
import sys

import oura_self_analysis as oura
from local_enrichment import (
    EXPORT_FOLDER, choose_sleep, daily_records, make_base, number,
    rnd, write_atomically,
)

ANALYTICS_VERSION = "1.0"
FEATURE_NAME = "health_features.csv"
INSIGHTS_NAME = "health_insights.json"

# Human-readable provenance, not mechanized clinical decision rules.
SOURCES = {
    "oura": "https://cloud.ouraring.com/v2/docs",
    "hr_validation": "https://doi.org/10.14814/phy2.70527",
    "hrv_quality": "https://doi.org/10.3390/s24237475",
    "sleep_regular": "https://doi.org/10.1093/sleep/zsad253",
}
FIELDS = [
    "day", "sleep_score", "sleep_minutes", "sleep_efficiency_pct",
    "sleep_latency_minutes", "bedtime_local", "wake_local",
    "bedtime_consistency_sd_minutes_14d", "sleep_minutes_avg_7d",
    "hrv_ms", "hrv_median_7d", "hrv_median_previous_28d",
    "hrv_change_pct", "rhr_bpm", "rhr_median_7d",
    "rhr_median_previous_28d", "rhr_change_bpm",
    "respiratory_rate_per_min", "training_sessions", "prior_day_training",
    "data_quality",
]


def plausible(value: object, low: float, high: float) -> float | None:
    n = number(value)
    return n if n is not None and low <= n <= high else None


def bedtime_minute(iso: object) -> float | None:
    """Minutes since local noon, wrapping smoothly through midnight.

    ISO with timezone offset required: local wall clock matters for regularity,
    while absolute UTC times would cause spurious shifts during DST.
    """
    if not isinstance(iso, str):
        return None
    try:
        parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return (parsed.hour * 60 + parsed.minute + parsed.second / 60 - 720) % 1440


def local_clock(iso: object) -> str | None:
    if bedtime_minute(iso) is None:
        return None
    parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return parsed.strftime("%H:%M")


def observation(series: dict[str, dict], day: date, field: str, *,
                days: int, include_today: bool, minimum: int,
                aggregate: str = "median") -> tuple[float | None, int]:
    """Calendar-window aggregation; missing dates are never backfilled."""
    offset = 0 if include_today else 1
    sample = [
        series.get((day - timedelta(days=i)).isoformat(), {}).get(field)
        for i in range(offset, days + offset)
    ]
    values = [float(v) for v in sample if isinstance(v, (float, int))
              and not isinstance(v, bool)]
    if len(values) < minimum:
        return None, len(values)
    return (median(values) if aggregate == "median" else mean(values)), len(values)


def training_by_day(path: Path, start: date, end: date) -> tuple[dict[str, int], bool]:
    """Workout day is the workout's own local day, not the sleep reporting day."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT day, payload FROM records WHERE collection='workout' "
            "AND day BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        )
        count: dict[str, int] = {}
        has_data = False
        for day, payload in rows:
            item = json.loads(payload)
            if not isinstance(item, dict) or not day:
                continue
            has_data = True
            count[day] = count.get(day, 0) + 1
        return count, has_data
    finally:
        con.close()


def primary_features(path: Path, days: int, today: date) -> tuple[list[dict], dict]:
    if not 7 <= days <= 90:
        raise oura.OuraError("Health analytics window must be 7–90 days.")
    if not path.is_file():
        raise oura.OuraError("No Oura SQLite database; sync the ring first.")
    start = today - timedelta(days=days - 1)
    # 28 preceding days are required for fair baseline comparison.
    records = daily_records(path, start - timedelta(days=28), today)
    training, training_available = training_by_day(
        path, start - timedelta(days=1), today)
    if not records:
        raise oura.OuraError("No Oura observations in the requested window.")
    base: dict[str, dict] = {}

    for key, groups in records.items():
        raw = make_base(key, groups)
        main = choose_sleep(groups.get("sleep", []))
        # Day, not bedtime start, is Oura's waking day for the main sleep.
        raw["sleep_minutes"] = plausible(raw["total_sleep_minutes"], 0, 1000)
        raw["sleep_score"] = plausible(raw["sleep_score"], 0, 100)
        raw["sleep_efficiency_pct"] = plausible(raw["sleep_efficiency_pct"], 0, 100)
        raw["hrv_ms"] = plausible(raw["average_hrv_ms"], 1, 250)
        raw["rhr_bpm"] = plausible(raw["lowest_heart_rate_bpm"], 25, 150)
        raw["respiratory_rate_per_min"] = plausible(main.get("average_breath"), 5, 40)
        latency = plausible(main.get("latency"), 0, 7200)
        raw["sleep_latency_minutes"] = rnd(latency / 60) if latency is not None else None
        raw["bedtime_local"] = local_clock(main.get("bedtime_start"))
        raw["wake_local"] = local_clock(main.get("bedtime_end"))
        raw["bedtime_minute"] = bedtime_minute(main.get("bedtime_start"))
        raw["main_sleep_present"] = bool(main)
        base[key] = raw

    result: list[dict] = []
    for index in range(days):
        current = start + timedelta(days=index)
        key = current.isoformat()
        b = base.get(key)
        if b is None or not any(b.get(k) is not None for k in (
                "sleep_score", "sleep_minutes", "hrv_ms", "rhr_bpm")):
            continue
        feature = {
            "day": key,
            "sleep_score": b.get("sleep_score"),
            "sleep_minutes": b.get("sleep_minutes"),
            "sleep_efficiency_pct": b.get("sleep_efficiency_pct"),
            "sleep_latency_minutes": b.get("sleep_latency_minutes"),
            "bedtime_local": b.get("bedtime_local"),
            "wake_local": b.get("wake_local"),
            "hrv_ms": b.get("hrv_ms"),
            "rhr_bpm": b.get("rhr_bpm"),
            "respiratory_rate_per_min": b.get("respiratory_rate_per_min"),
            "training_sessions": training.get(key) if training_available else None,
            "prior_day_training": (training.get((current - timedelta(days=1)).isoformat(), 0) > 0
                                   if training_available else None),
        }
        for metric, prefix in (("hrv_ms", "hrv"), ("rhr_bpm", "rhr")):
            recent, _ = observation(base, current, metric, days=7, include_today=True,
                                     minimum=5)
            previous, _ = observation(base, current, metric, days=28, include_today=False,
                                       minimum=14)
            feature[prefix + "_median_7d"] = rnd(recent) if recent is not None else None
            feature[prefix + "_median_previous_28d"] = rnd(previous) if previous is not None else None
            if recent is not None and previous is not None:
                if prefix == "hrv":
                    feature["hrv_change_pct"] = rnd((recent - previous) / previous * 100) if previous else None
                else:
                    feature["rhr_change_bpm"] = rnd(recent - previous)
            else:
                feature["hrv_change_pct" if prefix == "hrv" else "rhr_change_bpm"] = None

        recent_sleep, _ = observation(base, current, "sleep_minutes", days=7,
                                      include_today=True, minimum=4, aggregate="mean")
        feature["sleep_minutes_avg_7d"] = rnd(recent_sleep) if recent_sleep is not None else None
        bedtime_values = [
            base.get((current - timedelta(days=i)).isoformat(), {}).get("bedtime_minute")
            for i in range(14)
        ]
        bedtime_values = [x for x in bedtime_values if x is not None]
        # Clock values are linearized around noon. For unusual daytime sleep
        # schedules this proxy is not a validated Sleep Regularity Index.
        feature["bedtime_consistency_sd_minutes_14d"] = (
            rnd(pstdev(bedtime_values)) if len(bedtime_values) >= 7 else None)
        problems = []
        if not b["main_sleep_present"]:
            problems.append("no_main_sleep")
        if b.get("hrv_ms") is None:
            problems.append("missing_hrv")
        if feature["bedtime_local"] is None:
            problems.append("missing_timezone_or_bedtime")
        if not training_available:
            problems.append("workout_history_unavailable")
        feature["data_quality"] = ",".join(problems)
        result.append(feature)

    if not result:
        raise oura.OuraError("Insufficient local sleep data to compute features.")
    meta = {
        "window_start": start.isoformat(), "window_end": today.isoformat(),
        "calendar_days": days, "observed_days": len(result),
        "workout_history_available": training_available,
    }
    return result, meta


def insight(id: str, title: str, summary: str, *,
            dates: dict, observations: dict, sources: list[str],
            limitations: list[str]) -> dict:
    return {
        "id": id, "title": title, "summary": summary,
        "observation_window": dates, "measurements": observations,
        "evidence_urls": sources, "evidence_class": "exploratory",
        "medical_alert": False, "limitations": limitations,
    }


def make_insights(rows: list[dict], meta: dict) -> list[dict]:
    dates = {"start": meta["window_start"], "end": meta["window_end"]}
    recent_days = sorted(rows, key=lambda r: r["day"])[-7:]
    result = []

    sleep = [r["sleep_minutes"] for r in recent_days if r.get("sleep_minutes") is not None]
    if len(sleep) >= 4:
        result.append(insight(
            "sleep-duration", "Durata del sonno: ultimi 7 giorni",
            f"Media delle notti disponibili: {mean(sleep) / 60:.1f} ore; "
            "osservazione descrittiva, non una valutazione clinica.",
            dates=dates, observations={"mean_sleep_hours": round(mean(sleep) / 60, 2),
                                       "n_nights": len(sleep)},
            sources=[SOURCES["oura"]],
            limitations=["Il tempo dormito è una stima del dispositivo.",
                         "Le notti mancanti non sono conteggiate come zero."]))

    latest = sorted(rows, key=lambda r: r["day"])[-1]
    sd = latest.get("bedtime_consistency_sd_minutes_14d")
    if sd is not None:
        result.append(insight(
            "sleep-regularity", "Regolarità dell'orario di coricamento",
            f"Variabilità degli orari locali: deviazione standard {sd:.0f} minuti "
            "sulle osservazioni disponibili negli ultimi 14 giorni.",
            dates=dates, observations={"bedtime_sd_minutes": sd},
            sources=[SOURCES["sleep_regular"], SOURCES["oura"]],
            limitations=["Proxy dell'orario, non Sleep Regularity Index validato.",
                         "Un viaggio, il lavoro a turni e un cambio fuso possono distorcere il risultato."]))

    hrv_diff, rhr_diff = latest.get("hrv_change_pct"), latest.get("rhr_change_bpm")
    if hrv_diff is not None or rhr_diff is not None:
        measures = {
            "hrv_recent_median_ms": latest.get("hrv_median_7d"),
            "hrv_previous28_median_ms": latest.get("hrv_median_previous_28d"),
            "hrv_change_pct": hrv_diff,
            "rhr_recent_median_bpm": latest.get("rhr_median_7d"),
            "rhr_previous28_median_bpm": latest.get("rhr_median_previous_28d"),
            "rhr_change_bpm": rhr_diff,
        }
        parts = []
        if hrv_diff is not None:
            parts.append(f"HRV notturna mediana: {hrv_diff:+.1f}%")
        if rhr_diff is not None:
            parts.append(f"FC minima notturna mediana: {rhr_diff:+.1f} bpm")
        result.append(insight(
            "autonomic-trends", "Trend fisiologici rispetto alla baseline",
            "; ".join(parts) + " rispetto ai precedenti 28 giorni. "
            "Questi scostamenti da soli non indicano una patologia.",
            dates=dates, observations=measures,
            sources=[SOURCES["hr_validation"], SOURCES["hrv_quality"]],
            limitations=["HRV dipende anche da sonno, alcol, stress e carico sportivo.",
                         "Baseline minima: 14 notti precedenti; recenti: almeno 5."]))

    if meta.get("workout_history_available"):
        # Compare next-day sleep HRV to preceding workout day, not same-day.
        after = [r["hrv_ms"] for r in rows if r.get("prior_day_training") is True and
                 r.get("hrv_ms") is not None]
        without = [r["hrv_ms"] for r in rows if r.get("prior_day_training") is False and
                   r.get("hrv_ms") is not None]
        if len(after) >= 4 and len(without) >= 4:
            delta = rnd(median(after) - median(without))
            result.append(insight(
                "exercise-following-day", "HRV dopo giornate con allenamento",
                f"Mediana HRV al risveglio dopo giorni con allenamento: "
                f"{median(after):.1f} ms, contro {median(without):.1f} ms negli altri "
                "giorni disponibili. È solo un confronto osservazionale.",
                dates=dates, observations={
                    "next_day_hrv_after_workout_median_ms": rnd(median(after)),
                    "next_day_hrv_without_workout_median_ms": rnd(median(without)),
                    "difference_ms": delta, "n_post_training": len(after),
                    "n_other": len(without)},
                sources=[SOURCES["hr_validation"]],
                limitations=["I workout potrebbero non essere tutti registrati.",
                             "Non controlla intensità, sonno, giorno della settimana o altri fattori.",
                             "Non misura tempo di recupero né causalità."]))
    result.append(insight(
        "data-coverage", "Copertura dei dati fisiologici",
        f"{meta['observed_days']} giorni con osservazioni su "
        f"{meta['calendar_days']} giorni di calendario.",
        dates=dates, observations={
            "observed_days": meta["observed_days"],
            "calendar_days": meta["calendar_days"],
            "workout_history_available": meta["workout_history_available"]},
        sources=[SOURCES["oura"]],
        limitations=["Le osservazioni mancanti non sono interpolate.",
                     "L'assenza di workout non implica riposo se i dati non sono stati importati."]))
    return result


def analyze(path: Path, days: int = 30, *, today: date | None = None) -> tuple[list[dict], dict]:
    today = today or date.today()
    rows, meta = primary_features(path, days=days, today=today)
    return rows, {
        "schema_version": ANALYTICS_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "privacy": "Private local Oura analytics; never publish to GitHub",
        "method": "Deterministic descriptive analytics; no AI or clinical inference.",
        "metadata": meta,
        "insights": make_insights(rows, meta),
        "scientific_references": SOURCES,
    }


def export(path: Path, *, days: int = 30, output_dir: Path | None = None,
           today: date | None = None) -> tuple[Path, Path, dict]:
    rows, document = analyze(path, days, today=today)
    output_dir = output_dir or EXPORT_FOLDER
    csv_path, insights_path = output_dir / FEATURE_NAME, output_dir / INSIGHTS_NAME

    def write_csv(stream):
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row[key] for key in FIELDS})

    write_atomically(csv_path, write_csv)
    write_atomically(insights_path,
                     lambda stream: json.dump(document, stream, indent=2,
                                              ensure_ascii=False, allow_nan=False))
    return csv_path, insights_path, document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Oura local research-informed analytics")
    parser.add_argument("--days", type=int, default=30, help="7–90 day window")
    args = parser.parse_args(argv)
    try:
        csv_path, insights_path, report = export(oura.DB_PATH, days=args.days)
        print(f"Daily health features: {csv_path}")
        print(f"Explainable insights:   {insights_path}")
        for item in report["insights"]:
            print(f"• {item['title']}: {item['summary']}")
        return 0
    except (oura.OuraError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
