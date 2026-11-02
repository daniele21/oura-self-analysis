"""Shared, deterministic comparisons for sleep and autonomic recovery.

Three non-overlapping calendar-window comparisons. Missing data are never zero.
Statistical variation is not a clinical threshold or recovery diagnosis.
Private individual records are not returned by this module; only aggregates.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import cos, hypot, isfinite, log, pi, sin, sqrt
from statistics import mean, median
from typing import Mapping

# (key, human label, unit, central tendency).
SLEEP_METRICS = (
    ("sleep_minutes", "Durata del sonno", "min", "mean"),
    ("sleep_efficiency_pct", "Efficienza del sonno", "pp", "mean"),
    ("awake_minutes", "Tempo sveglio stimato", "min", "mean"),
    ("sleep_latency_minutes", "Latenza", "min", "mean"),
    ("sleep_score", "Sleep Score Oura", "pt", "mean"),
    ("deep_sleep_minutes", "Sonno profondo stimato", "min", "mean"),
    ("rem_sleep_minutes", "Sonno REM stimato", "min", "mean"),
    ("light_sleep_minutes", "Sonno leggero stimato", "min", "mean"),
    ("bedtime_local", "Regolarità orario a letto", "min SD", "circular_sd"),
    ("wake_local", "Regolarità orario risveglio", "min SD", "circular_sd"),
)
RECOVERY_METRICS = (
    ("hrv_ms", "HRV media notturna", "ms", "median"),
    ("rhr_bpm", "FC minima notturna", "bpm", "median"),
    ("sleep_minutes", "Durata sonno", "min", "median"),
    ("respiratory_rate_per_min", "Frequenza respiratoria", "atti/min", "median"),
)
WINDOWS = (
    ("7v7", 7, 7, 4, 4),
    ("7v28", 7, 28, 4, 14),
    ("28v28", 28, 28, 21, 21),
)
# Deliberately separate completeness gates: established 7/28 HRV reference.
RECOVERY_MIN_RECENT_7 = 5


def _valid(value: object, metric: str) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    if not isfinite(v):
        return None
    limits = {
        "sleep_minutes": (1, 1440),
        "sleep_efficiency_pct": (0, 100),
        "sleep_latency_minutes": (0, 120),
        "awake_minutes": (0, 1440),
        "sleep_score": (0, 100),
        "deep_sleep_minutes": (0, 1440),
        "rem_sleep_minutes": (0, 1440),
        "light_sleep_minutes": (0, 1440),
        "hrv_ms": (1, 250),
        "rhr_bpm": (25, 150),
        "respiratory_rate_per_min": (5, 40),
    }
    low, high = limits.get(metric, (-float("inf"), float("inf")))
    return v if low <= v <= high else None


def _clock(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        hour, minute = map(int, value.split(":"))
    except (TypeError, ValueError):
        return None
    return float(hour * 60 + minute) if 0 <= hour < 24 and 0 <= minute < 60 else None


def _circular_sd(minutes: list[float]) -> float | None:
    if len(minutes) < 2:
        return None
    angles = [x * 2 * pi / 1440 for x in minutes]
    resultant = hypot(mean(cos(x) for x in angles), mean(sin(x) for x in angles))
    if resultant < 1e-8:
        return None
    return sqrt(max(0, -2 * log(min(1.0, resultant)))) * 1440 / (2 * pi)


def _window(by_day: Mapping[str, dict], today: date, offset: int, length: int,
            key: str, method: str, minimum: int) -> tuple[dict, list[float | None]]:
    days = [today - timedelta(days=lag) for lag in range(offset + length - 1, offset - 1, -1)]
    raw = [by_day.get(d.isoformat(), {}).get(key) for d in days]
    series = [(_clock(x) if method == "circular_sd" else _valid(x, key)) for x in raw]
    values = [x for x in series if x is not None]
    center = None
    if len(values) >= minimum:
        if method == "circular_sd":
            center = _circular_sd(values)
        elif method == "median":
            center = median(values)
        else:
            center = mean(values)
    return ({
        "start": days[0].isoformat(), "end": days[-1].isoformat(),
        "calendar_days": length, "valid_nights": len(values),
        "coverage_pct": round(100 * len(values) / length, 1),
        "sufficient": center is not None,
        "value": round(center, 2) if center is not None else None,
    }, series)


def _persist(recent: list[float | None], baseline_center: float | None,
             difference: float | None) -> dict:
    """Direction support, not likelihood of a genuine trend or a health signal."""
    result = {"same_direction_n": None, "valid_n": len([x for x in recent if x is not None]),
              "longest_calendar_run": None, "same_direction_pct": None}
    if baseline_center is None or difference is None or abs(difference) < 1e-9:
        return result
    direction = 1 if difference > 0 else -1
    flags = [v is not None and (v - baseline_center) * direction > 0 for v in recent]
    count = sum(flags)
    run = longest = 0
    for flag in flags:
        run = run + 1 if flag else 0
        longest = max(run, longest)
    result.update(same_direction_n=count, longest_calendar_run=longest,
                  same_direction_pct=round(100 * count / result["valid_n"], 1)
                  if result["valid_n"] else None)
    return result


def _metric(by_day: Mapping[str, dict], today: date, spec: tuple,
            params: tuple, group: str) -> dict:
    key, label, unit, method = spec
    code, recent_days, reference_days, minimum_recent, minimum_reference = params
    if group == "recovery" and recent_days == 7:
        minimum_recent = RECOVERY_MIN_RECENT_7
    recent, recent_series = _window(by_day, today, 0, recent_days, key, method, minimum_recent)
    reference, reference_series = _window(by_day, today, recent_days, reference_days,
                                           key, method, minimum_reference)
    current, prior = recent["value"], reference["value"]
    # Direction for circular SD is a period-level comparison only, NOT a
    # comparison of individual bedtime clock minutes against the SD.
    delta = round(current - prior, 2) if current is not None and prior is not None else None
    reference_values = [v for v in reference_series if v is not None]
    spread = None
    shift = None
    if method != "circular_sd" and len(reference_values) >= minimum_reference:
        m = median(reference_values)
        spread = 1.4826 * median(abs(v - m) for v in reference_values)
        if spread > 1e-9 and delta is not None:
            shift = round(delta / spread, 2)
    persistence = (_persist(recent_series, prior, delta) if method != "circular_sd"
                   and recent["sufficient"] and reference["sufficient"] else None)
    return {
        "key": key, "label": label, "unit": unit, "aggregate": method,
        "recent": recent, "reference": reference, "delta": delta,
        "delta_percent": round(100 * delta / prior, 2) if delta is not None
                         and method != "circular_sd" and prior > 0 else None,
        "baseline_robust_sigma": round(spread, 2) if spread is not None else None,
        "shift_in_baseline_spreads": shift, "persistence": persistence,
        "status": "available" if delta is not None else "insufficient",
    }


def recent_week_trajectory(by_day: Mapping[str, dict], today: date,
                           specs: tuple, week_metrics: list[dict]) -> dict:
    """Predeclared, within-week comparison: 3 latest nights vs 4 earlier nights.

    The last three calendar nights must all have data, and three of the
    previous four must be present. No clinical interpretation or extrapolation.
    """
    weekly = {m["key"]: m for m in week_metrics}
    metrics = []
    for key, label, unit, method in specs:
        if method == "circular_sd":
            continue  # clock spread cannot be decomposed into single-night values
        tail, _ = _window(by_day, today, 0, 3, key, method, 3)
        first, _ = _window(by_day, today, 3, 4, key, method, 3)
        delta = (round(tail["value"] - first["value"], 2)
                 if tail["value"] is not None and first["value"] is not None else None)
        weekly_delta = weekly[key]["delta"]
        opposite = (delta * weekly_delta < 0 if delta is not None
                    and weekly_delta is not None else None)
        metrics.append({
            "key": key, "label": label, "unit": unit, "aggregate": method,
            "latest_three": tail, "earlier_four": first,
            "delta": delta, "opposes_weekly_comparison": opposite,
        })
    return {
        "recent_span": [(today - timedelta(days=2)).isoformat(), today.isoformat()],
        "earlier_span": [(today - timedelta(days=6)).isoformat(),
                         (today - timedelta(days=3)).isoformat()],
        "metrics": metrics,
        "limitations": (
            "Confronto esplorativo di 3 notti con 4, non un trend clinico; "
            "notti mancanti sopprimono la stima, non vengono interpolate."
        ),
    }


def build(rows: list[dict] | Mapping[str, dict], *, today: date, group: str) -> dict:
    """Return a window-aware, aggregate-only report, without leaking old daily rows."""
    if group not in ("sleep", "recovery"):
        raise ValueError("Unsupported comparison group")
    by_day = (rows if isinstance(rows, Mapping)
              else {r["day"]: r for r in rows if isinstance(r.get("day"), str)})
    if group == "sleep":
        # Sleep Score can exist without a qualifying main overnight session.
        # Keep all sleep metrics tied to the same long_sleep eligibility rule.
        by_day = {day: (row if row.get("main_sleep_available") is True else {})
                  for day, row in by_day.items()}
    specs = SLEEP_METRICS if group == "sleep" else RECOVERY_METRICS
    windows = {}
    for params in WINDOWS:
        code = params[0]
        metrics = [_metric(by_day, today, spec, params, group) for spec in specs]
        windows[code] = {
            "code": code, "recent_days": params[1], "reference_days": params[2],
            "metrics": metrics, "available_metrics": sum(m["status"] == "available" for m in metrics),
        }
    trajectory = recent_week_trajectory(by_day, today, specs, windows["7v7"]["metrics"])
    return {
        "schema_version": "1.1", "group": group, "windows": windows,
        "as_of_day": today.isoformat(),
        "recent_week_trajectory": trajectory,
        "default_window": "7v7" if group == "sleep" else "7v28",
        "privacy": "Aggregates only; older daily records are not exposed",
        "limitations": [
            "Periodi di calendario non sovrapposti, terminano al giorno di risveglio selezionato.",
            "Confronti esplorativi e non diagnostici; nessuna causalità o significatività statistica.",
            "MAD è un riferimento personale descrittivo, non una soglia clinica.",
            "La direzione delle differenze non equivale automaticamente a miglioramento.",
            "Il supporto di direzione conta le osservazioni individuali sopra o sotto il centro precedente.",
            "Le fasi del sonno sono stime del dispositivo, più incerte delle durate globali.",
            "Gli ultimi tre giorni sono confrontati con i quattro precedenti solo come descrizione.",
            "Il confronto è ancorato alla più recente osservazione utilizzabile, che può essere datata.",
        ],
    }
