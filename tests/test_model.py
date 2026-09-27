import unittest

import numpy as np
import pandas as pd

from helpers import ROOT  # noqa: F401  (sets sys.path)
from telco_churn import model


class MetricTests(unittest.TestCase):
    def test_auc_perfect_and_random(self):
        y = np.array([0, 0, 1, 1])
        self.assertEqual(model.roc_auc(y, np.array([0.1, 0.2, 0.8, 0.9])), 1.0)
        self.assertEqual(model.roc_auc(y, np.array([0.9, 0.8, 0.2, 0.1])), 0.0)
        self.assertAlmostEqual(model.roc_auc(y, np.array([0.5, 0.5, 0.5, 0.5])), 0.5)

    def test_classification_metrics(self):
        y = np.array([1, 0, 1, 0])
        p = np.array([0.9, 0.8, 0.2, 0.1])
        m = model.classification_metrics(y, p, 0.5)
        self.assertEqual(m["confusion"], {"tp": 1, "fp": 1, "fn": 1, "tn": 1})
        self.assertEqual(m["accuracy"], 0.5)

    def test_decile_lift_sums(self):
        rng = np.random.default_rng(0)
        p = rng.random(1000)
        y = (rng.random(1000) < p).astype(float)
        lift = model.decile_lift_table(y, p)
        self.assertEqual(len(lift), 10)
        self.assertEqual(lift["cumulative_churners_pct"].iloc[-1], 100.0)
        self.assertGreater(lift["lift"].iloc[0], lift["lift"].iloc[-1])

    def test_risk_band_boundaries(self):
        self.assertEqual(model.risk_band(0.0), "Low")
        self.assertEqual(model.risk_band(0.2), "Medium")
        self.assertEqual(model.risk_band(0.5), "High")
        self.assertEqual(model.risk_band(1.0), "High")


class NumpyLogitTests(unittest.TestCase):
    def test_recovers_separating_direction(self):
        rng = np.random.default_rng(1)
        X = rng.normal(size=(2000, 2))
        logits = 1.5 * X[:, 0] - 2.0 * X[:, 1]
        y = (rng.random(2000) < 1 / (1 + np.exp(-logits))).astype(float)
        m = model.NumpyLogisticRegression(l2=0.1).fit(X, y)
        self.assertGreater(m.coef_[0], 1.0)
        self.assertLess(m.coef_[1], -1.5)
        self.assertGreater(model.roc_auc(y, m.predict_proba(X)), 0.85)


class TrainingTests(unittest.TestCase):
    def test_train_on_synthetic_frame(self):
        rng = np.random.default_rng(2)
        n = 600
        df = pd.DataFrame({
            "tenure_months": rng.integers(0, 73, n),
            "monthly_charges": rng.uniform(18, 118, n),
            "num_addon_services": rng.integers(0, 7, n),
            "charge_ratio": 1.0,
            "contract": rng.choice(["Month-to-month", "One year", "Two year"], n),
            "internet_service": rng.choice(["DSL", "Fiber optic", "No"], n),
            "payment_method": rng.choice(["Electronic check", "Mailed check"], n),
        })
        df["total_charges"] = df["tenure_months"] * df["monthly_charges"]
        logit = -1 + 1.5 * (df["contract"] == "Month-to-month") - 0.04 * df["tenure_months"]
        df["churn_flag"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

        run = model.train_churn_model(df, "customer")
        self.assertEqual(len(run.probabilities), n)
        self.assertGreater(run.metrics["roc_auc_test"], 0.6)
        self.assertIn("contract_Two_year", set(run.drivers["feature"]))  # Month-to-month is the dropped baseline
        scored = model.attach_scores(df, run)
        self.assertEqual(set(scored["risk_band"]) - {"Low", "Medium", "High"}, set())


if __name__ == "__main__":
    unittest.main()
