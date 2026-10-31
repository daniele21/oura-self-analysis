"""Exercise Recovery 2.0: descriptive workout exposure and 1–3 wake-day response.

Reads Oura v2 'workout' records locally; never uses free-form labels or
exports timestamps, workout IDs, or individual exercise-event histories.
The response is observational: D+1/D+2/D+3 wake-day differences vs D.
It is NOT exact elapsed hours, causal recovery, overtraining or medical advice.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from statistics import median
import math

VALID_INTENSITY = {"easy", "moderate", "hard"}
MIN_EVENTS = 4
SOURCE = "https://cloud.ouraring.com/v2/docs"
EVIDENCE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC12787763/"
METHOD_EVIDENCE = "https://doi.org/10.1152/ajpheart.00041.2026"
OUTCOMES = {"hrv_ms": "ms", "rhr_bpm": "bpm", "sleep_minutes": "min"}
MAX_DURATION_MINUTES = 1440


def number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def category(activity: object) -> str:
    """Conservative buckets; do not infer CrossFit/Padel from unknown labels."""
    if not isinstance(activity, str):
        return "other"
    key = activity.strip().lower().replace("-", "_").replace(" ", "_")
    if key in {"cross_training", "crossfit", "circuit_training", "hiit", "high_intensity_interval_training"}:
        return "cross_training"
    if key in {"padel", "padel_tennis", "tennis", "squash", "badminton", "pickleball"}:
        return "racket_sport"
    if key in {"strength_training", "weight_training", "weightlifting", "strength", "functional_strength_training"}:
        return "strength"
    if key in {"running", "trail_running", "treadmill", "jogging"}:
        return "running"
    if key in {"cycling", "indoor_cycling", "mountain_biking", "spinning"}:
        return "cycling"
    if key in {"walking", "hiking", "nordic_walking"}:
        return "walking"
    return "other"


def duration_minutes(workout: dict) -> float | None:
    start, end = workout.get("start_datetime"), workout.get("end_datetime")
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return None
    if a.utcoffset() is None or b.utcoffset() is None:
        return None
    diff = (b - a).total_seconds() / 60
    return round(diff, 1) if 0 < diff <= MAX_DURATION_MINUTES else None


def read_workout_days(db: Path, start: date, end: date) -> dict[str, dict]:
    """Aggregated activity by Oura calendar date; no raw identifiers leave here."""
    if not db.is_file():
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    result: dict[str, dict] = {}
    try:
        for day, payload in con.execute(
            "SELECT day, payload FROM records WHERE collection='workout' "
            "AND day BETWEEN ? AND ?", (start.isoformat(), end.isoformat())
        ):
            if not day:
                continue
            try:
                item = json.loads(payload)
            except (TypeError, ValueError):
                continue
            if not isinstance(item, dict):
                continue
            agg = result.setdefault(day, {
                "sessions": 0, "duration_minutes": 0., "duration_n": 0,
                "intensity_n": 0, "hard_minutes": 0., "categories": {},
                "intensities": {},
            })
            agg["sessions"] += 1
            act = category(item.get("activity"))
            agg["categories"][act] = agg["categories"].get(act, 0) + 1
            intensity = item.get("intensity")
            if intensity not in VALID_INTENSITY:
                intensity = "unknown"
            agg["intensities"][intensity] = agg["intensities"].get(intensity, 0) + 1
            if intensity != "unknown":
                agg["intensity_n"] += 1
            minutes = duration_minutes(item)
            if minutes is not None:
                agg["duration_minutes"] += minutes
                agg["duration_n"] += 1
                if intensity == "hard":
                    agg["hard_minutes"] += minutes
        for agg in result.values():
            if not agg["duration_n"]:
                agg["duration_minutes"] = None
                agg["hard_minutes"] = None
            else:
                agg["duration_minutes"] = round(agg["duration_minutes"], 1)
                agg["hard_minutes"] = round(agg["hard_minutes"], 1)
        return result
    finally:
        con.close()


def daily_exposure(aggregates: dict[str, dict], day: str) -> dict:
    """Missing *workout records* never imply complete rest-day coverage."""
    raw = aggregates.get(day)
    if not raw:
        return {
            "workout_minutes_recorded": None,
            "workout_duration_sessions": 0,
            "workout_intensity_sessions": 0,
            "workout_hard_minutes_recorded": None,
            "workout_activity_group": None,
            "workout_intensity_category": None,
        }
    groups = list(raw["categories"])
    intensity = [key for key in raw["intensities"] if key != "unknown"]
    return {
        "workout_minutes_recorded": raw["duration_minutes"],
        "workout_duration_sessions": raw["duration_n"],
        "workout_intensity_sessions": raw["intensity_n"],
        "workout_hard_minutes_recorded": raw["hard_minutes"],
        "workout_activity_group": groups[0] if len(groups) == 1 else "mixed",
        "workout_intensity_category": intensity[0] if len(intensity) == 1 else "mixed" if len(intensity) > 1 else None,
    }


def event_curve(rows: list[dict], workouts: dict[str, dict],
                *, start: date, end: date) -> dict:
    """Avoid overlapping *recorded* workouts ±3 days for event comparisons.

    All counts are about recorded events. Unrecorded activity and confounders
    remain possible; intervals represent wake-day lags, not exact hours.
    """
    by_date = {row["day"]: row for row in rows}
    days = sorted(date.fromisoformat(day) for day in workouts
                  if start <= date.fromisoformat(day) <= end)
    eligible: list[date] = []
    incomplete = overlap = without_baseline = 0
    for day in days:
        if day > end - timedelta(days=3):
            incomplete += 1
            continue
        if any(other != day and abs((other - day).days) <= 3 for other in days):
            overlap += 1
            continue
        if day.isoformat() not in by_date or not any(
            number(by_date[day.isoformat()].get(k)) is not None for k in OUTCOMES
        ):
            without_baseline += 1
            continue
        eligible.append(day)

    def curve(events: list[date]) -> list[dict]:
        points = []
        for lag in (1, 2, 3):
            differences = {}
            for metric in OUTCOMES:
                samples = []
                for day in events:
                    base = by_date.get(day.isoformat(), {}).get(metric)
                    next_day = by_date.get((day + timedelta(days=lag)).isoformat(), {}).get(metric)
                    if number(base) is not None and number(next_day) is not None:
                        samples.append(float(next_day) - float(base))
                differences[metric + "_delta_median"] = round(median(samples), 2) if len(samples) >= MIN_EVENTS else None
                differences[metric + "_n"] = len(samples)
            points.append({"wake_day_lag": lag, **differences})
        return points

    groups: dict[str, list[date]] = {}
    intensities: dict[str, list[date]] = {}
    for day in eligible:
        item = workouts[day.isoformat()]
        kinds = list(item["categories"])
        if len(kinds) == 1:
            groups.setdefault(kinds[0], []).append(day)
        levels = [s for s in item["intensities"] if s != "unknown"]
        if len(levels) == 1 and item["intensity_n"] == item["sessions"]:
            intensities.setdefault(levels[0], []).append(day)

    return {
        "method": "recorded-workout-isolated-wake-day-lag",
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "recorded_workout_days": len(days),
        "eligible_isolated_days": len(eligible),
        "excluded_overlapping_days": overlap,
        "excluded_recent_days": incomplete,
        "excluded_no_baseline_days": without_baseline,
        "min_sample_per_lag": MIN_EVENTS,
        "outcomes": curve(eligible),
        "by_activity": [
            {"activity": key, "isolated_days": len(group), "outcomes": curve(group)}
            for key, group in sorted(groups.items())
            if len(group) >= MIN_EVENTS
        ],
        "by_intensity": [
            {"intensity": key, "isolated_days": len(group), "outcomes": curve(group)}
            for key, group in sorted(intensities.items())
            if len(group) >= MIN_EVENTS
        ],
        "quality": "exploratory" if len(eligible) >= MIN_EVENTS else "insufficient",
        "limitations": [
            "D+1/D+2/D+3 indicano risvegli nei tre giorni successivi, non ore esatte dal workout.",
            "Il confronto usa le misurazioni del giorno D come riferimento, non un valore pre-allenamento verificato.",
            "I workout registrati entro ±3 giorni sono esclusi per evitare sovrapposizioni note.",
            "L'assenza di un workout registrato non prova assenza di allenamento.",
            "Orari, intensità, sonno, trend stagionali e altri confondenti possono influire sui risultati.",
            "Le curve descrivono variazioni associative e non misurano un tempo clinico di recupero.",
        ],
        "evidence_urls": [EVIDENCE, METHOD_EVIDENCE],
    }


def recovery_insights(curve: dict) -> list[dict]:
    """Emit a transparent data sufficiency insight even if sample is too small."""
    dates = curve["window"]
    enough = curve["eligible_isolated_days"] >= MIN_EVENTS
    support = curve["eligible_isolated_days"]
    detail = (
        "Le differenze mediane per HRV, frequenza cardiaca minima e sonno sono disponibili "
        "per i singoli ritardi solo se esistono almeno quattro coppie di osservazioni."
        if enough else
        "Il numero di giornate isolate è insufficiente per stimare una curva di risposta."
    )
    return [{
        "id": "exercise-recovery-72h",
        "title": "Risposta fisiologica nei tre risvegli dopo workout",
        "summary": (
            f"{curve['recorded_workout_days']} giorni con workout registrati; "
            f"{support} giornate idonee al confronto, "
            f"{curve['excluded_overlapping_days']} escluse per allenamenti vicini. " + detail
        ),
        "observation_window": dates,
        "measurements": {
            "recorded_workout_days": curve["recorded_workout_days"],
            "eligible_isolated_days": support,
            "excluded_overlapping_days": curve["excluded_overlapping_days"],
            "excluded_recent_days": curve["excluded_recent_days"],
        },
        "quality": {
            "level": "limited" if enough else "insufficient",
            "recent_n": support,
            "method": curve["method"],
        },
        "interpretation": "I grafici mostrano differenze rispetto alla notte D. Non consentono di definire quanto tempo serve a recuperare.",
        "alternative_explanations": ["Altri workout non registrati", "Sonno e stress", "Variazioni nella routine"],
        "limitations": curve["limitations"],
        "evidence_urls": curve["evidence_urls"],
        "evidence_class": "exploratory",
        "medical_alert": False,
    }]
