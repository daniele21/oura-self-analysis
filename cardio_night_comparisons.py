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

from cardio_night_profiles import NightProfileError, build_profile, read_main_sleep

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




def _percentile(values: list[float], p: float) -> float:
    ordered=sorted(values)
    k=p*(len(ordered)-1)
    lo=int(k)
    hi=min(len(ordered)-1,lo+1)
    return ordered[lo]+(k-lo)*(ordered[hi]-ordered[lo])


def intranight_structure(profile: dict) -> dict:
    """Describe 30-minute windows only; no physiological/clinical low claim."""
    hr=[(b["elapsed_minutes"],b["heart_rate_bpm"]) for b in profile["bins"]
        if b["heart_rate_bpm"] is not None]
    out={"heart_rate":{
             "qualified_bins":len(hr),"minimum_bin_start_elapsed_minutes":None,
             "minimum_bin_median_bpm":None,"minimum_relative_position_pct":None,
             "median_bin_range_p90_minus_p10_bpm":None,
         },
         "hrv":{"qualified_bins":0,"median_bin_range_p90_minus_p10_ms":None},
         "method":"30-minute bin medians; minimum bin and 10th–90th percentile spread",
         "limitations":[
             "Il minimo è il minore fra le mediane di 30 minuti disponibili, non il minimo battito della notte.",
             "Servono almeno otto intervalli validi per stimare l'ampiezza fra percentili.",
             "La posizione del minimo dipende da durata, lacune, fasi del sonno e qualità del sensore.",
             "Questi indicatori non misurano stress, malattia o tempi di recupero.",
         ]}
    if len(hr)>=4:
        earliest=min(hr,key=lambda point:(point[1],point[0]))
        out["heart_rate"].update({
            "minimum_bin_start_elapsed_minutes":earliest[0],
            "minimum_bin_median_bpm":round(earliest[1],2),
            "minimum_relative_position_pct":round(
                min(100,(earliest[0]+profile["bin_minutes"]/2)/
                    profile["duration_minutes"]*100),1),
        })
    if len(hr)>=8:
        samples=[v for _,v in hr]
        out["heart_rate"]["median_bin_range_p90_minus_p10_bpm"]=round(
            _percentile(samples,.9)-_percentile(samples,.1),2)
    hrv=[b["hrv_ms"] for b in profile["bins"] if b["hrv_ms"] is not None]
    out["hrv"]["qualified_bins"]=len(hrv)
    if len(hrv)>=8:
        out["hrv"]["median_bin_range_p90_minus_p10_ms"]=round(
            _percentile(hrv,.9)-_percentile(hrv,.1),2)
    return out

def comparison(db: Path, waking_day: str) -> dict | None:
    """Return one selected night with contextual *aggregate-only* comparisons."""
    end = date.fromisoformat(waking_day)
    selected = _profile(db, end)
    if selected is None:
        return None
    prior = []
    for lag in range(1, MAX_DAYS + 1):
        d = end - timedelta(days=lag)
        try:
            prev = _profile(db, d)
        except NightProfileError:
            # A malformed historical night must not hide the selected one.
            prev = None
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
        "intranight": intranight_structure(selected),
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
