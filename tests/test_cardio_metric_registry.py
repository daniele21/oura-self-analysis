"""Canonical cardiovascular measurement meanings and dashboard contract tests."""
from pathlib import Path
import unittest

from cardio_metric_registry import METRICS, public_definitions


class TestCardiovascularRegistry(unittest.TestCase):
    def test_distinguish_nightly_minimum_mean_and_sample_series(self):
        self.assertEqual(METRICS["rhr_bpm"].source_field, "lowest_heart_rate")
        self.assertEqual(METRICS["hrv_ms"].source_field, "average_hrv")
        self.assertEqual(METRICS["heart_rate_series_bpm"].source_field, "heart_rate")
        self.assertEqual(METRICS["hrv_series_ms"].source_field, "hrv")
        self.assertEqual(METRICS["hrv_series_ms"].granularity, "sample_series")
        self.assertEqual(METRICS["hrv_ms"].granularity, "sleep_session")
        self.assertNotEqual(METRICS["rhr_bpm"].statistic, METRICS["average_heart_rate_bpm"].statistic)

    def test_registry_is_public_metadata_only(self):
        exported=public_definitions()
        self.assertIn("hrv_ms",exported)
        self.assertEqual(exported["hrv_ms"]["unit"],"ms")
        self.assertNotIn("id",exported["hrv_ms"])
        self.assertNotIn("samples",exported["hrv_ms"])
        self.assertNotIn("user",str(exported).lower())


if __name__=="__main__":
    unittest.main()
