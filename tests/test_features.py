import unittest

from helpers import kpi_frame, raw_frame
from telco_churn import clean, features


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.clean, _ = clean.clean_telco(raw_frame())

    def test_tenure_buckets(self):
        self.assertEqual(features.tenure_bucket(0), "00-12 months")
        self.assertEqual(features.tenure_bucket(12), "00-12 months")
        self.assertEqual(features.tenure_bucket(13), "13-24 months")
        self.assertEqual(features.tenure_bucket(72), "49-72 months")

    def test_customer_features(self):
        f = features.add_customer_features(self.clean).set_index("customer_id")
        self.assertEqual(f.loc["0001-AAAAA", "num_addon_services"], 2)   # backup + streaming tv
        self.assertEqual(f.loc["0003-CCCCC", "num_addon_services"], 0)
        self.assertEqual(f.loc["0003-CCCCC", "has_internet"], 0)
        self.assertEqual(f.loc["0003-CCCCC", "is_auto_payment"], 1)
        self.assertEqual(f.loc["0001-AAAAA", "is_month_to_month"], 1)
        self.assertAlmostEqual(f.loc["0003-CCCCC", "lifetime_avg_monthly"], 90.0)
        self.assertAlmostEqual(f.loc["0003-CCCCC", "charge_ratio"], 1.0)

    def test_network_aggregates_and_score(self):
        kpis = kpi_frame(["0001-AAAAA", "0003-CCCCC"])
        f = features.build_features(self.clean, kpis).set_index("customer_id")
        self.assertEqual(f.loc["0001-AAAAA", "kpi_months"], 12)
        self.assertEqual(f.loc["0002-BBBBB", "kpi_months"], 0)                 # no telemetry → 0, not NaN
        self.assertEqual(f.loc["0002-BBBBB", "network_quality_band"], "No telemetry")
        self.assertEqual(f.loc["0001-AAAAA", "network_complaints"], 1)
        self.assertGreater(f.loc["0001-AAAAA", "dropped_call_trend_pp"], 0)    # KPIs worsen over time in fixture
        score = f.loc["0001-AAAAA", "network_quality_score"]
        self.assertTrue(0 <= score <= 100)
        self.assertIn(f.loc["0001-AAAAA", "network_quality_band"], {"Poor", "Fair", "Good", "Excellent"})

    def test_features_without_kpis(self):
        f = features.build_features(self.clean, None)
        self.assertNotIn("network_quality_score", f.columns)
        self.assertEqual(len(f), 3)


if __name__ == "__main__":
    unittest.main()
