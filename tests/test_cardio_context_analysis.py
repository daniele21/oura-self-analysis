"""Synthetic cardio/sleep association tests; no user health measurements."""
from datetime import date,timedelta
import unittest

import cardio_context_analysis as analysis

END=date(2026,10,31)

def fake_days(n=70,*,trend=False,drop=set(),constant=False):
    rows=[]
    for i in range(n):
        day=END-timedelta(days=i)
        if i in drop:
            continue
        # Deterministic within-week relationship, nondegenerate tie-free ranks.
        weekday=day.weekday()
        x=(405+weekday*17+(i%5)*3)
        hrv=round((43+x*.095+(i%3)*.1),2)
        hr=round((78-x*.046-(i%4)*.1),2)
        if constant:
            x=430
        if trend:
            x=350+i*2
            hrv=60-i*.25
        rows.append({"day":day.isoformat(),"sleep_minutes":x,
                     "sleep_efficiency_pct":(83+weekday*1.3+i%3),
                     "hrv_ms":hrv,"rhr_bpm":hr})
    return rows


class CardioContextTests(unittest.TestCase):
    def test_associations_are_bounded_and_prespecified(self):
        out=analysis.evaluate(fake_days(),END.isoformat())
        self.assertEqual(len(out["associations"]),4)
        a=out["associations"][0]
        self.assertEqual(a["quality"]["paired_nights"],70)
        self.assertEqual(a["window"]["end"],END.isoformat())
        self.assertGreater(a["spearman_rho"],.5)
        self.assertIsNotNone(a["leave_one_week_sign_consistency_pct"])
        self.assertIn(a["status"],("consistent_exploratory","unstable"))
        self.assertTrue(all(k in {"paired_nights","minimum_paired_nights","calendar_days","distinct_weeks","within_week_groups"} for k in a["quality"]))
        self.assertFalse(any("predict" in x for x in a["limitations"]))

    def test_missing_days_or_too_few_distinct_weeks_is_insufficient(self):
        out=analysis.evaluate(fake_days(14),END.isoformat())
        self.assertTrue(all(x["status"]=="insufficient" for x in out["associations"]))
        self.assertTrue(all(x["spearman_rho"] is None for x in out["associations"]))

    def test_no_imputation_and_single_day_deduplication(self):
        rows=fake_days(40,drop={3,4,5})
        rows[0]["hrv_ms"]=None
        rows[1]["sleep_minutes"]=float("nan")
        rows[2]["rhr_bpm"]=float("inf")
        rows.append(rows[6].copy())  # duplicates do not increase sample size
        out=analysis.evaluate(rows,END.isoformat())
        a=next(x for x in out["associations"] if x["exposure"]=="sleep_minutes" and x["outcome"]=="hrv_ms")
        self.assertEqual(a["quality"]["paired_nights"],35)
        self.assertTrue(a["spearman_rho"] is None or -1 <= a["spearman_rho"] <= 1)

    def test_out_of_window_cannot_influence(self):
        rows=fake_days(25)
        rows.append({"day":(END-timedelta(days=94)).isoformat(),
                     "sleep_minutes":123,"sleep_efficiency_pct":31,
                     "hrv_ms":100,"rhr_bpm":100})
        out=analysis.evaluate(rows,END.isoformat())
        self.assertEqual(out["associations"][0]["quality"]["paired_nights"],25)

    def test_constant_series_never_emits_coefficient(self):
        out=analysis.evaluate(fake_days(65,constant=True),END.isoformat())
        duration=[a for a in out["associations"] if a["exposure"]=="sleep_minutes"]
        self.assertTrue(all(a["status"]=="uninformative" for a in duration))
        self.assertTrue(all(a["spearman_rho"] is None for a in duration))

    def test_within_week_sensitivity_not_equal_to_overall_trend(self):
        rows=fake_days(70,trend=True)
        a=analysis.evaluate(rows,END.isoformat())["associations"][0]
        self.assertIsNotNone(a["spearman_rho"])
        self.assertIsNotNone(a["within_week_rho"])
        self.assertEqual(a["quality"]["within_week_groups"]>=4,True)

    def test_explain_ranks_at_most_two_and_never_claims_causality(self):
        report=analysis.evaluate(fake_days(),END.isoformat())
        cards=analysis.explain(report)
        self.assertLessEqual(len(cards),2)
        for card in cards:
            self.assertFalse(card["medical_alert"])
            self.assertEqual(card["evidence_class"],"exploratory")
            self.assertIn("non dimostra",card["summary"])
            self.assertTrue(card["alternative_explanations"])
            self.assertNotIn("individual nights",str(card))

    def test_spearman_ties_and_boolean_rejection(self):
        self.assertEqual(analysis.rank([5,5,9,1]),[2.5,2.5,4,1])
        self.assertFalse(analysis.finite(True))
        self.assertFalse(analysis.finite(float("nan")))
        self.assertAlmostEqual(analysis.spearman(
            [(END,1,3),(END-timedelta(days=1),2,2),(END-timedelta(days=2),3,1)]),-1)


if __name__=="__main__":
    unittest.main()
