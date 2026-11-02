"""Transparent, non-clinical editorial selection from existing dashboard aggregates.

Only predeclared comparisons are selected; no new health scores or medical
risk predictions. Never use raw records or hidden historical daily observations.
"""
from __future__ import annotations

from datetime import date


def _metric(report: dict | None, window: str, key: str) -> dict | None:
    if not isinstance(report, dict):
        return None
    return next((m for m in report.get("windows", {}).get(window, {}).get("metrics", [])
                 if m.get("key") == key and m.get("status") == "available"), None)


def _tail(report: dict | None, key: str) -> dict | None:
    if not isinstance(report, dict):
        return None
    return next((m for m in report.get("recent_week_trajectory", {}).get("metrics", [])
                 if m.get("key") == key and m.get("delta") is not None), None)


def _reference(report: dict, recent: dict, baseline: dict) -> dict:
    return {
        "as_of_day": report.get("as_of_day"),
        "recent_window": [recent.get("start"), recent.get("end")],
        "reference_window": [baseline.get("start"), baseline.get("end")],
        "recent_valid_nights": recent.get("valid_nights"),
        "reference_valid_nights": baseline.get("valid_nights"),
    }


def build(payload: dict) -> dict:
    """Return up to two distinct, explainable patterns (priority is editorial).

    Suppress insufficient or unanchored patterns. Relative ordering does not
    grade physiology, assign clinical significance or rank health risk.
    """
    sleep = (payload.get("sleep_intelligence") or {}).get("comparisons")
    recovery = payload.get("period_comparisons")
    latest = payload.get("meta", {}).get("last_observed_day")
    patterns: list[dict] = []
    sleep_week = _metric(sleep, "7v7", "sleep_minutes")
    tail = _tail(sleep, "sleep_minutes")
    # Predeclared criteria: eligible full 3-night tail, >=3 preceding nights,
    # 6/7 recent and 6/7 reference in the 7v7 comparison.
    if sleep_week and tail and tail.get("opposes_weekly_comparison") is True:
        r, b = sleep_week["recent"], sleep_week["reference"]
        short_r, short_b = tail["latest_three"], tail["earlier_four"]
        if (r["valid_nights"] >= 6 and b["valid_nights"] >= 6
                and short_r["valid_nights"] == 3 and short_b["valid_nights"] >= 3):
            patterns.append({
                "id": "weekly-masks-recent-sleep-shift",
                "area": "sleep",
                "title": "La settimana e le ultime tre notti raccontano due andamenti diversi",
                "summary": "La durata media delle ultime tre notti si è mossa nella direzione opposta al confronto complessivo fra settimane. Approfondisci il dettaglio giornaliero prima di interpretare la media.",
                "priority_reason": "La direzione del confronto di tre notti contraddice quella di due settimane complete; è una priorità di lettura, non un allarme.",
                "measurements": {
                    "week_delta_minutes": sleep_week["delta"],
                    "latest_three_vs_earlier_four_minutes": tail["delta"],
                    "latest_three_nights": short_r["valid_nights"],
                    "earlier_four_nights": short_b["valid_nights"],
                },
                "quality": _reference(sleep, r, b),
                "limitations": [
                    "Tre e quattro notti rappresentano campioni piccoli e potenzialmente autocorrelati.",
                    "La differenza non identifica cause o una variazione clinicamente significativa.",
                ],
                "medical_alert": False,
                "evidence_class": "descriptive",
            })
    hrv, hr = _metric(recovery, "7v28", "hrv_ms"), _metric(recovery, "7v28", "rhr_bpm")
    if hrv and hr and (
        (hrv["delta"] < 0 and hr["delta"] > 0) or
        (hrv["delta"] > 0 and hr["delta"] < 0)
    ):
        # Quality gate stricter than basic availability: 6/7+21/28
        # observations for BOTH paired metrics; do not imply paired counts.
        if all(m["recent"]["valid_nights"] >= 6 and
               m["reference"]["valid_nights"] >= 21 for m in (hrv, hr)):
            patterns.append({
                "id": "hrv-hr-joint-direction",
                "area": "recovery",
                "title": "HRV e frequenza cardiaca minima si sono mosse in direzioni opposte",
                "summary": "Le mediane di HRV e frequenza cardiaca minima mostrano differenze di segno opposto rispetto ai precedenti 28 giorni. Esamina le curve notturne e il contesto, senza attribuire automaticamente una causa.",
                "priority_reason": "Due segnali autonomici cambiano insieme rispetto alla baseline personale, con copertura sufficiente in entrambi.",
                "measurements": {
                    "hrv_delta_ms": hrv["delta"],
                    "lowest_hr_delta_bpm": hr["delta"],
                },
                "quality": {
                    **_reference(recovery, hrv["recent"], hrv["reference"]),
                    "hr_valid_recent": hr["recent"]["valid_nights"],
                    "hr_valid_reference": hr["reference"]["valid_nights"],
                    "paired_nights_verified": False,
                },
                "limitations": [
                    "Le numerosità delle singole metriche non dimostrano l'accoppiamento notte-per-notte.",
                    "HRV e FC minima non sono un indice diagnostico né una misura diretta del recupero muscolare.",
                ],
                "medical_alert": False,
                "evidence_class": "descriptive",
            })
    # Do not promote stale measurements as current. We still provide their
    # dated historical interpretation, and let the UI explain the timestamp.
    return {
        "schema_version": "1",
        "as_of_day": latest,
        "age_days": payload.get("meta", {}).get("age_days"),
        "review_status": "historical" if payload.get("meta", {}).get("age_days") is not None
                           and payload["meta"]["age_days"] > 2 else "current_snapshot",
        "selection_method": "two predeclared pattern families, source coverage and non-overlapping calendar windows",
        "patterns": patterns[:2],
        "limitations": "Priorità di lettura, non classifica clinica. L'assenza di pattern non garantisce benessere o recupero.",
    }
