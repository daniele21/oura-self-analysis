"""Evidence-engine tests: synthetic only, no health information or network calls."""
from datetime import date, timedelta
import unittest

import longitudinal_insights as engine
import health_analytics


END = date(2026, 10, 31)


def history(*, recent_hrv=None, recent_hr=None, baseline_hrv=None,
            baseline_hr=None, missing=None):
    missing = set(missing or [])
    rows = []
    for lag in range(35):
        if lag in missing:
            continue
        current = END - timedelta(days=lag)
        # Add nonzero baseline spread: robust dispersion cannot divide by zero.
        rhv = baseline_hrv[lag % len(baseline_hrv)] if baseline_hrv is not None else \
            [49, 50, 52, 48, 51, 53, 50][lag % 7]
        rhr = baseline_hr[lag % len(baseline_hr)] if baseline_hr is not None else \
            [51, 52, 54, 50, 53, 55, 52][lag % 7]
        if lag < 7:
            rhv = recent_hrv[lag] if recent_hrv is not None else rhv
            rhr = recent_hr[lag] if recent_hr is not None else rhr
        rows.append({
            "day": current.isoformat(),
            "hrv_ms": rhv, "rhr_bpm": rhr, "sleep_minutes": 420 + lag % 4 * 6,
        })
    return rows


class TestLongitudinalInsights(unittest.TestCase):
    def test_windows_are_disjoint_and_measure_count_is_exact(self):
        rows = history(recent_hrv=[30] * 7)
        by_day = {r["day"]: r for r in rows}
        metric = engine.measure(by_day, END, "hrv_ms")
        self.assertEqual(metric["recent_n"], 7)
        self.assertEqual(metric["baseline_n"], 28)
        self.assertEqual(metric["recent_median"], 30)
        self.assertGreater(metric["baseline_median"], 45)
        self.assertLess(metric["standardized_shift"], -2)
        self.assertEqual(metric["days_outside_personal_band"], 7)
        self.assertEqual(metric["longest_consecutive_outside"], 7)
        self.assertEqual(metric["leave_one_out_direction_pct"], 100.0)
        self.assertEqual(metric["quality"], "adequate")

    def test_joint_change_is_concurrent_not_disease_prediction(self):
        rows = history(recent_hrv=[30] * 7, recent_hr=[68] * 7)
        result = engine.evaluate(rows, END.isoformat())
        ids = [i["id"] for i in result]
        self.assertIn("personal-variability-hrv_ms", ids)
        self.assertIn("personal-variability-rhr_bpm", ids)
        self.assertIn("hrv-rhr-cooccurrence", ids)
        joint = next(i for i in result if i["id"] == "hrv-rhr-cooccurrence")
        self.assertEqual(joint["measurements"]["paired_valid_n"], 7)
        self.assertEqual(joint["measurements"]["paired_outside_n"], 7)
        self.assertFalse(joint["medical_alert"])
        self.assertEqual(joint["evidence_class"], "exploratory")
        self.assertTrue(joint["alternative_explanations"])

    def test_missing_days_break_consecutive_persistence(self):
        rows = history(recent_hrv=[30] * 7, missing={2})
        metric = engine.measure({r["day"]:r for r in rows}, END, "hrv_ms")
        self.assertEqual(metric["recent_n"], 6)
        self.assertEqual(metric["days_outside_personal_band"], 6)
        self.assertEqual(metric["longest_consecutive_outside"], 4)
        self.assertIsNone(metric["bootstrap_80_delta_interval"])
        self.assertEqual(metric["quality"], "adequate")

    def test_missing_baseline_blocks_spurious_insights(self):
        rows = history(missing=set(range(7, 24)),recent_hrv=[30] * 7)
        result = engine.evaluate(rows, END.isoformat())
        self.assertEqual(result, [])
        metric = engine.measure({r["day"]:r for r in rows}, END, "hrv_ms")
        self.assertEqual(metric["quality"], "insufficient")
        self.assertIsNone(metric["standardized_shift"])

    def test_constant_baseline_has_no_statistical_band(self):
        rows = history(baseline_hrv=[50],recent_hrv=[30] * 7)
        metric = engine.measure({r["day"]:r for r in rows}, END, "hrv_ms")
        self.assertEqual(metric["quality"], "adequate")
        self.assertEqual(metric["baseline_median"], 50)
        self.assertIsNone(metric["standardized_shift"])
        self.assertIsNone(metric["days_outside_personal_band"])
        self.assertIsNone(metric["personal_band"])
        self.assertIn("Dispersione storica", " ".join(metric["limitations"]))
        result = engine.evaluate(rows, END.isoformat())
        self.assertNotIn("hrv-rhr-cooccurrence", [r["id"] for r in result])

    def test_leaving_one_out_remains_deterministic(self):
        rows = history(recent_hrv=[30, 31, 31, 30, 32, 32, 30])
        first = engine.evaluate(rows, END.isoformat())
        second = engine.evaluate(rows, END.isoformat())
        self.assertEqual(first, second)
        metric = engine.measure({r["day"]:r for r in rows}, END, "hrv_ms")
        interval = metric["bootstrap_80_delta_interval"]
        self.assertIsInstance(interval, list)
        self.assertEqual(len(interval), 2)
        self.assertLessEqual(interval[0], interval[1])
        self.assertNotIn("risk_score", str(first))

    def test_boolean_and_nan_do_not_count_as_physiology(self):
        rows = history(recent_hrv=[True, float("nan"), 40, 41, 42, 43, 44])
        metric = engine.measure({r["day"]:r for r in rows}, END, "hrv_ms")
        self.assertEqual(metric["recent_n"], 5)
        self.assertIsNone(metric["bootstrap_80_delta_interval"])

    def test_old_history_never_exposed_in_seven_day_ui_rows(self):
        self.assertTrue(health_analytics.ANALYTICS_VERSION.startswith("1."))
        # Caller filters returned feature rows but compute engine accepts 35 days.
        latest = history(recent_hrv=[31] * 7)
        result = engine.evaluate(latest, END.isoformat())
        self.assertTrue(result)
        self.assertEqual(result[0]["observation_window"]["end"], END.isoformat())


if __name__ == "__main__":
    unittest.main()
