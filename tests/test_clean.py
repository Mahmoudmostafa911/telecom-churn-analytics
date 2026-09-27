import unittest

from helpers import raw_frame
from telco_churn import clean, config


class CleanTests(unittest.TestCase):
    def setUp(self):
        self.df, self.report = clean.clean_telco(raw_frame())

    def test_columns_are_snake_case(self):
        self.assertIn("customer_id", self.df.columns)
        self.assertIn("tenure_months", self.df.columns)
        self.assertNotIn("customerID", self.df.columns)
        self.assertEqual(set(config.COLUMN_RENAMES.values()) | {"churn_flag"}, set(self.df.columns))

    def test_blank_total_charges_imputed_to_zero_for_tenure_zero(self):
        row = self.df.loc[self.df["customer_id"] == "0002-BBBBB"].iloc[0]
        self.assertEqual(row["tenure_months"], 0)
        self.assertEqual(row["total_charges"], 0.0)
        self.assertEqual(self.report.total_charges_blank, 1)
        self.assertEqual(self.report.total_charges_imputed_zero, 1)

    def test_numeric_types(self):
        self.assertTrue(str(self.df["monthly_charges"].dtype).startswith("float"))
        self.assertTrue(str(self.df["total_charges"].dtype).startswith("float"))
        self.assertTrue(str(self.df["tenure_months"].dtype).startswith("int"))

    def test_senior_citizen_conformed_to_yes_no(self):
        self.assertEqual(set(self.df["senior_citizen"]), {"Yes", "No"})

    def test_churn_flag(self):
        flags = dict(zip(self.df["customer_id"], self.df["churn_flag"]))
        self.assertEqual(flags["0001-AAAAA"], 1)
        self.assertEqual(flags["0002-BBBBB"], 0)

    def test_duplicates_removed(self):
        raw = raw_frame([{}, {}])  # same customer twice
        df, report = clean.clean_telco(raw)
        self.assertEqual(len(df), 1)
        self.assertEqual(report.duplicates_removed, 1)

    def test_unknown_category_is_reported_not_silently_dropped(self):
        raw = raw_frame([{"Contract": "Weekly"}])
        df, report = clean.clean_telco(raw)
        self.assertEqual(report.unknown_category_values.get("contract"), ["Weekly"])
        self.assertEqual(len(df), 1)

    def test_unparseable_total_with_tenure_is_estimated(self):
        raw = raw_frame([{"TotalCharges": "n/a", "tenure": "10", "MonthlyCharges": "50"}])
        df, report = clean.clean_telco(raw)
        self.assertEqual(report.total_charges_unparseable, 1)
        self.assertAlmostEqual(df["total_charges"].iloc[0], 500.0)


if __name__ == "__main__":
    unittest.main()
