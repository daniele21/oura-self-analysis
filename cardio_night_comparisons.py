"""Deterministic, bounded cross-night HR/HRV comparison.

Compare the selected Oura main sleep with:
- the *exact* preceding waking date (never the nearest available night);
- median at the same elapsed-from-bedtime 30-minute bin across prior 7
  calendar days, with >=4 independently qualified nights per bin;
- selected night first/second half using >=2 qualified bins per half.

No raw samples, workout timestamps, or identifying record IDs leave this module.
Missingness and changing night length are never interpolated. This is
exploratory, not a physiological/clinical recovery assessment.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from statistics import median

from cardio_night_profiles import build_profile, read_main_sleep

FIELDS = ("heart_rate_bpm", "hrv_ms")
MIN_WEEK_NIGHTS = 4
MIN_PAIRED_BINS = 4
MIN_HALF_BINS = 2
MAX_DAYS = 7


def _med(values: list[float], minimum: int) -> float | None:
    return round(median(values), 2) if len(values) >= minimum else None


def _profile(db: Path, waking_day: date) -> dict | None:
    session = read_main_sleep(db, waking_day.isoformat())
    if session is None:
        return None
    return build_profile(session, waking_day.isoformat())


def _half_profile(profile: dict) -> dict:
    """Halves of *time in bed*, not measured sleep phases or SRI."""
    midpoint = profile["duration_minutes"] / 2
    result = {}
    for field in FIELDS:
        earlier = []
        later = []
        for b in profile["bins"]:
            value = b[field]
            if value is None:
                continue
            # Bins are assigned using the center of their elapsed window;
            # the very last partial interval stays in its starting half.
            center = min(b["elapsed_minutes"] + profile["bin_minutes"] / 2,
                         profile["duration_minutes"])
            if center < midpoint:
                earlier.append(value)
            else:
                later.append(value)
        first = _med(earlier, MIN_HALF_BINS)
        second = _med(later, MIN_HALF_BINS)
        result[field] = {
            "first_half_median": first,
            "second_half_median": second,
            "second_minus_first": round(second - first, 2)
            if first is not None and second is not None else None,
            "first_half_valid_bins": len(earlier),
            "second_half_valid_bins": len(later),
            "sufficient": first is not None and second is not None,
        }
    return result


def _paired_summary(selected: dict, reference: list[dict], field: str) -> dict:
    """Only bins at identical elapsed positions are compared."""
    differences = []
    for current, other in zip(selected["bins"], reference):
        v, prev = current[field], other[field]
        if v is not None and prev is not None:
            differences.append(round(v - prev, 2))
    return {
        "paired_bins": len(differences),
        "median_delta": _med(differences, MIN_PAIRED_BINS),
        "min_paired_bins": MIN_PAIRED_BINS,
    }


def comparison(db: Path, waking_day: str) -> dict | None:
    """Return one selected night with contextual *aggregate-only* comparisons."""
    end = date.fromisoformat(waking_day)
    selected = _profile(db, end)
    if selected is None:
        return None
    prior = []
    for lag in range(1, MAX_DAYS + 1):
        d = end - timedelta(days=lag)
        prev = _profile(db, d)
        prior.append(prev)
    yesterday = prior[0]
    # Only aggregate same elapsed 30-minute bins (up to 48).
    reference = []
    for idx in range(len(selected["bins"])):
        row = {"elapsed_minutes": idx * selected["bin_minutes"]}
        for field in FIELDS:
            values = [
                p["bins"][idx][field] for p in prior
                if p is not None and idx < len(p["bins"])
                and p["bins"][idx][field] is not None
            ]
            row[field + "_n"] = len(values)
            row[field] = _med(values, MIN_WEEK_NIGHTS)
        reference.append(row)
    comparison_bins = []
    yesterday_bins = yesterday["bins"] if yesterday else []
    for idx, b in enumerate(selected["bins"]):
        other = yesterday_bins[idx] if idx < len(yesterday_bins) else None
        comparison_bins.append({
            "elapsed_minutes": b["elapsed_minutes"],
            "heart_rate_bpm": other["heart_rate_bpm"] if other else None,
            "hrv_ms": other["hrv_ms"] if other else None,
        })
    summaries = {}
    for field in FIELDS:
        summaries[field] = {
            "previous_day": _paired_summary(selected, comparison_bins, field),
            "previous_7": _paired_summary(selected, reference, field),
            "prior7_nights_with_usable_channel": sum(
                bool(p and p["channels"]["heart_rate" if field == "heart_rate_bpm"
                                       else "hrv"]["usable"]) for p in prior
            ),
        }
    selected["comparison"] = {
        "version": "1.0",
        "previous_day": {
            "day": (end - timedelta(days=1)).isoformat(),
            "available": yesterday is not None,
            "bins": comparison_bins,
        },
        "previous_7": {
            "start": (end - timedelta(days=7)).isoformat(),
            "end": (end - timedelta(days=1)).isoformat(),
            "nights_with_main_sleep": sum(p is not None for p in prior),
            "min_nights_per_bin": MIN_WEEK_NIGHTS,
            "bins": reference,
        },
        "selected_halves": _half_profile(selected),
        "deltas": summaries,
        "method": "exact preceding waking day; previous 7 independent nights at equal elapsed-from-bedtime bins",
        "limitations": [
            "Il confronto della notte precedente usa esclusivamente il giorno D-1; notti mancanti non vengono sostituite.",
            "Il profilo settimanale è una mediana delle 7 notti di calendario precedenti, per intervallo, con almeno 4 notti valide.",
            "L'asse temporale è il tempo trascorso da quando ci si è coricati; notti più corte non vengono interpolate.",
            "La differenza fra le due metà riguarda il tempo a letto e non distingue le fasi REM o profondo.",
            "Le differenze dei profili non sono un indice clinico di recupero e non identificano causalità.",
        ],
    }
    return selected
