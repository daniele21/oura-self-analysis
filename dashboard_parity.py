"""Check that the private dashboard API, its insight measurements and nightly
detail agree. No network access. Only structural discrepancies are returned.
"""
from __future__ import annotations

from datetime import date
from math import isfinite

from dashboard_insight_review import build as expected_review

MEASURES = (
    ("sleep_minutes", "sleep_minutes"),
    ("sleep_efficiency_pct", "sleep_efficiency_pct"),
    ("sleep_score", "sleep_score"),
    ("hrv_ms", "hrv_ms"),
    ("rhr_bpm", "heart_rate_min_bpm"),
    ("deep_sleep_minutes", "deep_sleep_minutes"),
    ("rem_sleep_minutes", "rem_sleep_minutes"),
    ("light_sleep_minutes", "light_sleep_minutes"),
)
MISMATCH_CODES = {
    "OUT_OF_RANGE", "NIGHT_RECORD_DIFFERENCE", "WEEKLY_INSIGHT_DIFFERENCE",
    "BASELINE_INSIGHT_DIFFERENCE", "REVIEW_INCONSISTENT",
    "COMPARISON_RANGE_DRIFT", "INVALID_DATE",
}


def _number(v: object) -> float | None:
    return float(v) if isinstance(v, (float, int)) and not isinstance(v, bool)         and isfinite(v) else None


def _same(a: object, b: object, tolerance: float = 0.06) -> bool:
    x, y = _number(a), _number(b)
    return x is None and y is None if x is None or y is None else abs(x - y) <= tolerance


def _flag(items: list[dict], code: str, **details) -> None:
    # No physiological measurements or source record IDs in problems;
    # only metric and view identifiers.
    items.append({"code": code, **details})


def inspect_payload(payload: dict) -> tuple[int, list[dict]]:
    """Independent checks against API-visible records and structured insights."""
    checks = 0
    issues: list[dict] = []
    start, end = payload["range"]["start"], payload["range"]["end"]
    dates = sorted(x["day"] for x in payload["records"])
    if any(d < start or d > end for d in dates) or len(dates) != len(set(dates)):
        _flag(issues, "OUT_OF_RANGE", scope="records")
    checks += 1
    last = dates[-1] if dates else None
    if payload["meta"]["last_observed_day"] != last:
        _flag(issues, "OUT_OF_RANGE", scope="last_observation")
    checks += 1
    nights = payload.get("sleep_intelligence", {}).get("nights", [])
    by_day = {r["day"]: r for r in payload["records"]}
    for night in nights:
        day = night["day"]
        checks += 1
        if day < start or day > end:
            _flag(issues, "OUT_OF_RANGE", scope="sleep_night")
            continue
        if night.get("main_sleep_available") is not True or day not in by_day:
            continue
        row = by_day[day]
        for visible, sleep_key in MEASURES:
            checks += 1
            if not _same(row.get(visible), night.get(sleep_key)):
                _flag(issues, "NIGHT_RECORD_DIFFERENCE", metric=visible)
    insights = {i["id"]: i for i in payload.get("insights", [])}
    report = payload.get("sleep_intelligence") or {}
    weekly = report.get("weekly") or {}
    weekly_claim = insights.get("sleep-weekly-comparison")
    if weekly_claim:
        measures = weekly_claim.get("measurements") or {}
        delta = weekly.get("delta_recent_vs_previous", {})
        checks += 3
        if not _same(measures.get("sleep_minutes_avg_delta"), delta.get("sleep_minutes")):
            _flag(issues, "WEEKLY_INSIGHT_DIFFERENCE", metric="sleep_minutes")
        if not _same(measures.get("current_nights"), weekly.get("recent", {}).get("available_nights"), 0):
            _flag(issues, "WEEKLY_INSIGHT_DIFFERENCE", metric="current_nights")
        if not _same(measures.get("previous_nights"), weekly.get("previous", {}).get("available_nights"), 0):
            _flag(issues, "WEEKLY_INSIGHT_DIFFERENCE", metric="previous_nights")
    else:
        checks += 1
        if weekly.get("delta_recent_vs_previous", {}).get("sleep_minutes") is not None:
            _flag(issues, "WEEKLY_INSIGHT_DIFFERENCE", metric="missing_weekly_card")
    comparison = payload.get("period_comparisons", {})
    if comparison.get("as_of_day") == payload["range"]["end"]:
        metrics = {m["key"]: m for m in comparison.get("windows", {}).get("7v28", {}).get("metrics", [])}
        for key in ("hrv_ms", "rhr_bpm", "sleep_minutes"):
            claim = insights.get("personal-variability-" + key)
            metric = metrics.get(key)
            if not claim or not metric:
                continue
            values = claim.get("measurements", {})
            # Longitudinal sleep uses a median, as does the recovery view;
            # the standalone sleep comparison uses a mean and is NOT comparable.
            for claim_key, comparison_key in (("recent_median", "recent"), ("baseline_median", "reference")):
                checks += 1
                if not _same(values.get(claim_key), metric[comparison_key]["value"]):
                    _flag(issues, "BASELINE_INSIGHT_DIFFERENCE", metric=key)
    checks += 1
    if payload.get("review") != expected_review(payload):
        _flag(issues, "REVIEW_INCONSISTENT", scope="editorial_selection")
    return checks, issues


def inspect_ranges(payloads: dict[int, dict]) -> tuple[int, list[dict]]:
    """Same source history must yield the same *aggregate* comparisons, even
    when the API hides older day-level records for 7- or 30-day views.
    Suppress this parity test if a window has no recent observations.
    """
    checks = 0
    issues = []
    for domain, path in (
        ("sleep", lambda p: p["sleep_intelligence"]["comparisons"]),
        ("recovery", lambda p: p["period_comparisons"]),
    ):
        reports = [(days, path(payload)) for days, payload in payloads.items()]
        for i in range(len(reports)):
            for j in range(i + 1, len(reports)):
                days_a, a = reports[i]
                days_b, b = reports[j]
                if a["as_of_day"] != b["as_of_day"]:
                    continue  # Views are not comparable when last-night coverage differs.
                for period in ("7v7", "7v28", "28v28"):
                    left = {m["key"]: m for m in a["windows"][period]["metrics"]}
                    right = {m["key"]: m for m in b["windows"][period]["metrics"]}
                    for key, x in left.items():
                        checks += 1
                        y = right[key]
                        if (x["status"] != y["status"] or
                                x["recent"]["valid_nights"] != y["recent"]["valid_nights"] or
                                x["reference"]["valid_nights"] != y["reference"]["valid_nights"] or
                                not _same(x["delta"], y["delta"])):
                            _flag(issues, "COMPARISON_RANGE_DRIFT",
                                  group=domain, period=period, metric=key,
                                  ranges=[days_a, days_b])
    return checks, issues


def is_structural_problem(issue: dict) -> bool:
    return issue.get("code") in MISMATCH_CODES
