import unittest

import pandas as pd

from helpers import kpi_frame, raw_frame
from telco_churn import clean, features, quality


class QualityGateTests(unittest.TestCase):
    def setUp(self):
        c, _ = clean.clean_telco(raw_frame())
        self.kpis = kpi_frame(["0001-AAAAA", "0002-BBBBB", "0003-CCCCC"])
        self.feats = features.build_features(c, self.kpis)

    def test_clean_data_has_no_fail(self):
        dq = quality.run_quality_gate(self.feats, self.kpis, expected_rows=3)
        self.assertFalse((dq["status"] == "FAIL").any())
        self.assertIn("run_ts", dq.columns)
        self.assertGreater(len(dq), 30)

    def test_row_count_mismatch_is_only_a_warning(self):
        dq = quality.run_quality_gate(self.feats, self.kpis, expected_rows=7043)
        row = dq[dq["check_name"] == "row_count"].iloc[0]
        self.assertEqual(row["status"], "WARN")

    def test_orphan_kpi_rows_fail(self):
        bad = pd.concat([self.kpis, kpi_frame(["9999-ZZZZZ"], months=1)])
        with self.assertRaises(quality.DataQualityError):
            quality.run_quality_gate(self.feats, bad)
        dq = quality.run_quality_gate(self.feats, bad, fail_on_error=False)
        self.assertEqual(dq.loc[dq["check_name"] == "fk_customer_id_exists", "status"].iloc[0], "FAIL")

    def test_duplicate_key_fails(self):
        dup = pd.concat([self.feats, self.feats.iloc[[0]]])
        with self.assertRaises(quality.DataQualityError):
            quality.run_quality_gate(dup, None)

    def test_unknown_domain_value_fails(self):
        bad = self.feats.copy()
        bad.loc[0, "contract"] = "Weekly"
        dq = quality.run_quality_gate(bad, None, fail_on_error=False)
        self.assertEqual(dq.loc[dq["check_name"] == "domain_contract", "status"].iloc[0], "FAIL")


if __name__ == "__main__":
    unittest.main()
