"""Deterministic, non-clinical longitudinal insights for personal Oura signals.

Use individual non-overlapping calendar windows, robust spread and sensitivity
checks. Statistical flags are NOT clinical thresholds or medical alerts.
Only standard-library Python; no external calls or models.
"""
from __future__ import annotations

from datetime import date, timedelta
import math
import random
from statistics import mean, median, pstdev

WINDOW_RECENT = 7
WINDOW_BASELINE = 28
MAD_FACTOR = 1.4826
MIN_RECENT = 5
MIN_BASELINE = 14
BOOTSTRAP_REPS = 300

SOURCES = {
    "hrv_review": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12787763/",
    "hrv_guidelines": "https://www.ais.gov.au/__data/assets/pdf_file/0013/1130260/HRV-BPG_FINAL.pdf",
    "sleep": "https://doi.org/10.1093/sleep/zsad253",
}
METRICS = {
    "hrv_ms": ("HRV notturna", "ms"),
    "rhr_bpm": ("FC minima notturna", "bpm"),
    "sleep_minutes": ("Durata del sonno", "min"),
}


def valid(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def calendar_values(rows_by_day: dict, end: date, field: str, offset: int, length: int) -> list[float | None]:
    result = []
    for lag in range(offset, offset + length):
        row = rows_by_day.get((end - timedelta(days=lag)).isoformat(), {})
        value = row.get(field)
        result.append(float(value) if valid(value) else None)
    return result


def median_abs_deviation(values: list[float]) -> float:
    center = median(values)
    return median(abs(value - center) for value in values)


def percentile(sorted_values: list[float], fraction: float) -> float:
    index = fraction * (len(sorted_values) - 1)
    left = int(index)
    right = min(len(sorted_values) - 1, left + 1)
    return sorted_values[left] + (index - left) * (sorted_values[right] - sorted_values[left])


def resample_blocks(values: list[float], length: int, rng: random.Random) -> list[float]:
    """Circular moving-block bootstrap, preserving adjacency within blocks."""
    out = []
    n = len(values)
    while len(out) < n:
        start = rng.randrange(n)
        out.extend(values[(start + j) % n] for j in range(length))
    return out[:n]


def bootstrap_interval(recent: list[float | None],
                       baseline: list[float | None]) -> list[float] | None:
    """Exploratory 80% resampling interval on median difference.

    Only when the entire 35-day calendar has observations: we never
    concatenate values across unknown missing dates. Not a clinical CI.
    """
    if any(v is None for v in recent + baseline):
        return None
    rng = random.Random(24680)  # exact repeatability, never implicit global state
    differences = []
    for _ in range(BOOTSTRAP_REPS):
        r = resample_blocks(recent, 3, rng)
        b = resample_blocks(baseline, 3, rng)
        differences.append(median(r) - median(b))
    differences.sort()
    return [round(percentile(differences, .1), 2),
            round(percentile(differences, .9), 2)]


def leave_one_out_consistency(recent: list[float], baseline_median: float) -> float | None:
    """Fraction of 7-day jackknife medians that retain the observed direction."""
    if len(recent) < 5:
        return None
    full = median(recent) - baseline_median
    if abs(full) < 1e-10:
        return None
    same = 0
    for i in range(len(recent)):
        change = median(recent[:i] + recent[i+1:]) - baseline_median
        if change * full > 0:
            same += 1
    return round(100 * same / len(recent), 1)


def longest_run(daily_flags: list[bool]) -> int:
    longest = current = 0
    for flagged in daily_flags:
        current = current + 1 if flagged else 0
        longest = max(longest, current)
    return longest


def measure(rows_by_day: dict, end: date, field: str) -> dict:
    recent = calendar_values(rows_by_day, end, field, 0, WINDOW_RECENT)
    baseline = calendar_values(rows_by_day, end, field, WINDOW_RECENT, WINDOW_BASELINE)
    r = [v for v in recent if v is not None]
    b = [v for v in baseline if v is not None]
    measured = {
        "metric": field,
        "unit": METRICS[field][1],
        "recent_n": len(r), "recent_days": WINDOW_RECENT,
        "baseline_n": len(b), "baseline_days": WINDOW_BASELINE,
        "recent_coverage_pct": round(len(r) / WINDOW_RECENT * 100, 1),
        "baseline_coverage_pct": round(len(b) / WINDOW_BASELINE * 100, 1),
        "recent_median": None, "baseline_median": None,
        "absolute_change": None, "percentage_change": None,
        "baseline_mad": None, "baseline_robust_sigma": None,
        "standardized_shift": None, "recent_cv_pct": None,
        "days_outside_personal_band": None, "longest_consecutive_outside": None,
        "leave_one_out_direction_pct": None, "bootstrap_80_delta_interval": None,
        "personal_band": None,
        "quality": "insufficient",
        "limitations": [],
    }
    if len(r) < MIN_RECENT or len(b) < MIN_BASELINE:
        measured["limitations"].append("Campione insufficiente: sono necessari almeno 5/7 e 14/28 giorni.")
        return measured
    rv, bv = median(r), median(b)
    delta = rv - bv
    spread = MAD_FACTOR * median_abs_deviation(b)
    measured.update({
        "recent_median": round(rv, 2), "baseline_median": round(bv, 2),
        "absolute_change": round(delta, 2),
        "percentage_change": round(delta * 100 / bv, 2) if abs(bv) > 1e-12 else None,
        "baseline_mad": round(median_abs_deviation(b), 3),
        "baseline_robust_sigma": round(spread, 3),
        "recent_cv_pct": round(pstdev(r) / mean(r) * 100, 2) if len(r) > 1 and mean(r) > 0 else None,
        "leave_one_out_direction_pct": leave_one_out_consistency(r, bv),
        "bootstrap_80_delta_interval": bootstrap_interval(recent, baseline),
    })
    measured["quality"] = "adequate" if len(r) >= 6 and len(b) >= 21 else "limited"
    if measured["quality"] == "limited":
        measured["limitations"].append("Copertura parziale: l'incertezza potrebbe essere sottostimata.")
    measured["limitations"].append(
        "Le notti consecutive non sono indipendenti e le condizioni possono cambiare nel tempo.")
    if measured["bootstrap_80_delta_interval"] is not None:
        measured["limitations"].append(
            "L'intervallo bootstrap 80% è esplorativo: non è un intervallo clinico né una probabilità di malattia.")
    if spread <= 1e-9:
        measured["limitations"].append(
            "Dispersione storica nulla o trascurabile: nessuna classificazione di scostamento insolito.")
        return measured
    # A robust reference band on historical daily values, NOT a validated health threshold.
    lower, upper = bv - 2 * spread, bv + 2 * spread
    measured["personal_band"] = [round(lower, 2), round(upper, 2)]
    measured["standardized_shift"] = round(delta / spread, 2)
    # The window is in reverse chronological order. Missing days break a streak.
    flags = [v is not None and (v < lower or v > upper) for v in recent]
    measured["days_outside_personal_band"] = sum(flags)
    measured["longest_consecutive_outside"] = longest_run(flags)
    measured["limitations"].append(
        "La banda mediana ±2×MAD scalata è un riferimento statistico individuale, non una soglia medica.")
    return measured


def _make_insight(key: str, title: str, summary: str, measures: dict,
                  dates: dict, limitations: list[str], evidence_urls: list[str],
                  quality: dict, interpretation: str, alternatives: list[str]) -> dict:
    return {
        "id": key, "title": title, "summary": summary,
        "observation_window": dates,
        "measurements": measures,
        "quality": quality,
        "interpretation": interpretation,
        "alternative_explanations": alternatives,
        "limitations": limitations,
        "evidence_urls": evidence_urls,
        "evidence_class": "exploratory",
        "medical_alert": False,
    }


def evaluate(history: list[dict], window_end: str) -> list[dict]:
    """Explainable statistical assessments at the specified reporting date.

    history may contain more than the current UI range; no additional data is
    emitted to the dashboard except aggregate evidence for the end date.
    """
    end = date.fromisoformat(window_end)
    by_day = {row["day"]: row for row in history if isinstance(row.get("day"), str)}
    dates = {
        "start": (end - timedelta(days=34)).isoformat(),
        "end": end.isoformat(),
        "recent": [(end - timedelta(days=6)).isoformat(), end.isoformat()],
        "baseline": [(end - timedelta(days=34)).isoformat(),
                     (end - timedelta(days=7)).isoformat()],
    }
    analyses = {name: measure(by_day, end, name) for name in METRICS}
    result = []
    for metric_name, info in analyses.items():
        if info["quality"] == "insufficient":
            continue
        title, unit = METRICS[metric_name]
        change = info["absolute_change"]
        direction = "superiore" if change > 0 else "inferiore" if change < 0 else "in linea"
        summary = (
            f"{title}: mediana recente {info['recent_median']:g} {unit}, "
            f"baseline {info['baseline_median']:g} {unit} "
            f"({change:+g} {unit}). Variabilità recente CV: "
            f"{info['recent_cv_pct']:g}%." if info["recent_cv_pct"] is not None else
            f"{title}: confronto con la baseline disponibile."
        )
        if info["standardized_shift"] is None:
            interpretation = (
                "La variabilità della baseline non consente di definire una banda "
                "statistica individuale attendibile. Descrizione del cambiamento soltanto."
            )
        else:
            interpretation = (
                f"Il valore recente è {direction} alla baseline. "
                f"{info['days_outside_personal_band']} delle ultime "
                f"{WINDOW_RECENT} giornate sono fuori dalla banda statistica personale; "
                f"massima sequenza consecutiva {info['longest_consecutive_outside']}."
            )
        alternatives = ([
            "Sonno e routine alterati", "Allenamento o recupero", "Alcol o stress",
            "Malessere, farmaci o qualità del sensore"
        ] if metric_name != "sleep_minutes" else [
            "Impegni e orari", "Viaggi o turni", "Artefatti del sensore"
        ])
        result.append(_make_insight(
            "personal-variability-" + metric_name,
            title + ": variabilità personale",
            summary,
            {k: v for k, v in info.items() if k not in ("limitations",)},
            dates,
            info["limitations"],
            [SOURCES["hrv_review"], SOURCES["hrv_guidelines"]]
            if metric_name != "sleep_minutes" else [SOURCES["sleep"]],
            {"level": info["quality"], "recent_n": info["recent_n"],
             "baseline_n": info["baseline_n"],
             "recent_coverage_pct": info["recent_coverage_pct"],
             "baseline_coverage_pct": info["baseline_coverage_pct"],
             "method": "robust baseline + leave-one-out + optional block bootstrap"},
            interpretation,
            alternatives
        ))
    # Concurrence is reported descriptively, never as "infection" or clinical risk.
    hrv, rhr = analyses["hrv_ms"], analyses["rhr_bpm"]
    if all(a["quality"] != "insufficient" and a["personal_band"] is not None for a in (hrv, rhr)):
        hrv_band_low = hrv["personal_band"][0]
        rhr_band_high = rhr["personal_band"][1]
        hrv_values = calendar_values(by_day, end, "hrv_ms", 0, WINDOW_RECENT)
        rhr_values = calendar_values(by_day, end, "rhr_bpm", 0, WINDOW_RECENT)
        paired_count = sum(v is not None and h is not None for v, h in zip(hrv_values, rhr_values))
        paired_outside = sum(
            v is not None and h is not None and v < hrv_band_low and h > rhr_band_high
            for v, h in zip(hrv_values, rhr_values)
        )
        if paired_count >= 5:
            result.append(_make_insight(
                "hrv-rhr-cooccurrence",
                "HRV e frequenza cardiaca: andamento congiunto",
                f"Nelle ultime 7 giornate: {paired_outside}/{paired_count} notti con "
                "HRV sotto e FC minima sopra le rispettive bande statistiche personali. "
                "Il conteggio non è una previsione medica.",
                {"paired_valid_n": paired_count, "paired_outside_n": paired_outside,
                 "hrv_personal_lower_ms": hrv_band_low,
                 "rhr_personal_upper_bpm": rhr_band_high},
                dates,
                ["Bande derivate da MAD, non da studi clinici.",
                 "Le metriche possono muoversi insieme per molte cause non misurate.",
                 "Dati mancanti, autocorrelazione e allenamenti limitano l'interpretazione."],
                [SOURCES["hrv_review"], SOURCES["hrv_guidelines"]],
                {"level": "adequate" if paired_count >= 6 and
                 all(a["quality"] == "adequate" for a in (hrv, rhr)) else "limited",
                 "recent_n": paired_count, "baseline_n": min(hrv["baseline_n"], rhr["baseline_n"]),
                 "method": "paired days vs individual robust bands"},
                "Co-occorrenza osservata dei due segnali, non un indice di malattia.",
                ["Carico sportivo", "Orari e qualità del sonno",
                 "Alcol, stress e possibili variazioni del sensore"],
            ))
    return result
