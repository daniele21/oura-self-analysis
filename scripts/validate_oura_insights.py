#!/usr/bin/env python3
"""Private, local-only QA of Oura sleep/recovery comparisons.

Reads the existing SQLite database without modifying it. Stores aggregate
results and explanatory checks under the user's application support folder.
Stdout is deliberately free of physiological values, dates and record IDs.
Do NOT run this on an untrusted shared runner or upload its private JSON.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import tempfile
import sys

# Direct invocation from scripts/ must still import the pinned repository code.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import health_analytics
import oura_self_analysis as oura
import dashboard_server
from dashboard_parity import inspect_payload, inspect_ranges, is_structural_problem

DEFAULT_OUTPUT = (Path.home() / "Library" / "Application Support"
                  / "OuraSelfAnalysis" / "enriched" / "quality_review.json")


def validate_report(report: dict, group: str) -> tuple[int, list[dict]]:
    checks = 0
    issues: list[dict] = []
    if report.get("group") != group:
        issues.append({"code": "GROUP_MISMATCH", "scope": group})
    as_of = date.fromisoformat(report["as_of_day"])
    for code, window in report["windows"].items():
        for metric in window["metrics"]:
            checks += 1
            a, b = metric["recent"], metric["reference"]
            try:
                recent_start, reference_end = date.fromisoformat(a["start"]), date.fromisoformat(b["end"])
                if reference_end >= recent_start:
                    raise ValueError("overlap")
                if date.fromisoformat(a["end"]) != as_of:
                    raise ValueError("unaligned")
                if not 0 <= a["valid_nights"] <= a["calendar_days"]:
                    raise ValueError("invalid_recent_coverage")
                if not 0 <= b["valid_nights"] <= b["calendar_days"]:
                    raise ValueError("invalid_reference_coverage")
                if (metric["status"] == "available") != (a["value"] is not None and b["value"] is not None):
                    raise ValueError("wrong_status")
                if metric["delta"] is not None and abs(
                    metric["delta"] - round(a["value"] - b["value"], 2)
                ) > 0.011:
                    raise ValueError("wrong_delta")
            except (ValueError, TypeError, KeyError) as exc:
                issues.append({
                    "code": "COMPARISON_INCONSISTENCY",
                    "scope": group, "period": code, "metric": metric["key"],
                    "type": type(exc).__name__,
                })
    return checks, issues


def audit(db: Path, *, today: date) -> dict:
    # At most 90 recent calendar days; calculations may read earlier history,
    # but no individual sleep/HRV/HR record is retained in the report.
    _, document = health_analytics.analyze(db, days=90, today=today)
    reports = {
        "sleep": document["sleep_intelligence"]["comparisons"],
        "recovery": document["period_comparisons"],
    }
    passed = 0
    issues = []
    observations = []
    for group, report in reports.items():
        count, problems = validate_report(report, group)
        passed += count
        issues.extend(problems)
        as_of = date.fromisoformat(report["as_of_day"])
        trajectory = report["recent_week_trajectory"]
        mixed = [m for m in trajectory["metrics"]
                 if m.get("opposes_weekly_comparison") is True]
        missing = [m["key"] for m in report["windows"]["7v7"]["metrics"]
                   if m["status"] == "insufficient"]
        observations.append({
            "area": group,
            "as_of_day": report["as_of_day"],
            "lag_calendar_days": (today - as_of).days,
            "missing_week_comparisons": missing,
            "short_term_vs_weekly_disagreements": [
                {"metric": m["key"], "tail_delta": m["delta"],
                 "weekly_delta": next(
                     x["delta"] for x in report["windows"]["7v7"]["metrics"]
                     if x["key"] == m["key"]),
                 "latest_three_valid_nights": m["latest_three"]["valid_nights"],
                 "earlier_four_valid_nights": m["earlier_four"]["valid_nights"]}
                for m in mixed
            ],
            "main_metrics": {
                metric["key"]: {
                    "recent": metric["recent"],
                    "reference": metric["reference"],
                    "delta": metric["delta"],
                    "persistence": metric["persistence"],
                }
                for metric in report["windows"][report["default_window"]]["metrics"]
                if metric["key"] in (
                    "sleep_minutes", "sleep_efficiency_pct", "hrv_ms", "rhr_bpm"
                )
            },
        })
    # Verify the same local SQLite through all three dashboard view ranges.
    # API payloads stay in RAM and never appear in CI logs or shared files.
    payloads = {days: dashboard_server.make_payload(db, days=days, today=today)
                for days in dashboard_server.SUPPORTED_DAYS}
    api_checks = 0
    for days, payload in payloads.items():
        checked, discrepancies = inspect_payload(payload)
        api_checks += checked
        issues.extend({**item, "visible_range_days": days} for item in discrepancies)
    checked, discrepancies = inspect_ranges(payloads)
    api_checks += checked
    issues.extend(discrepancies)
    if any(o["lag_calendar_days"] > 2 for o in observations):
        issues.append({"code": "DATA_NOT_CURRENT",
                       "scope": "data_freshness",
                       "explanation": "Comparisons describe the last measured night, not today's physiological state."})
    return {
        "schema_version": "1", "report_date": today.isoformat(),
        "clinical_guidance": False, "causal_inference": False,
        "scope": "local read-only self-audit; aggregates only",
        "checks_executed": passed, "api_checks_executed": api_checks,
        "api_ranges_checked": list(payloads), "issues": issues,
        "observations": observations,
        "limitations": [
            "Review comparisons are observational; missingness and wearables introduce uncertainty.",
            "A 3-vs-4-day disagreement is an exploratory descriptive flag, not a medical alert.",
            "No user-level diagnostic or training recommendations are inferred.",
            "This private file contains health aggregates and must not be uploaded to GitHub.",
        ],
    }


def private_write(path: Path, data: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".quality-review-", suffix=".json", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2, ensure_ascii=False, allow_nan=False)
            out.write("\n")
        os.replace(tmp, path)
        path.chmod(0o600)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private local Oura comparison audit")
    parser.add_argument("--db", type=Path, default=oura.DB_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    try:
        result = audit(args.db, today=args.today)
        private_write(args.output, result)
    except (OSError, ValueError, KeyError, TypeError, oura.OuraError):
        # Errors may contain DB paths or personal data; avoid reproducing them
        # in a runner log. Run this locally, inspecting the private DB if needed.
        print("AUDIT_FAILED; private details were not printed")
        return 1
    failures = sum(item["code"] in ("COMPARISON_INCONSISTENCY", "GROUP_MISMATCH") or
                   is_structural_problem(item) for item in result["issues"])
    print(f"AUDIT_{'FAILED' if failures else 'COMPLETED'} "
          f"comparison_checks={result['checks_executed']} "
          f"api_checks={result['api_checks_executed']} inconsistencies={failures}")
    print("Aggregate report saved under the private local Application Support directory.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
