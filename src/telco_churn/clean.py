"""Cleaning & conformance of the raw Telco file.

What this step fixes (all of it is documented in ``CleaningReport`` so the
numbers can be quoted in the data-quality log):

* ``TotalCharges`` arrives as text and contains blank cells for customers with
  ``tenure == 0`` (11 rows in the IBM file). They are cast to numeric and the
  blanks are imputed as 0.0 — the customer has simply not been billed yet.
* ``SeniorCitizen`` is 0/1 while every other flag is Yes/No → conformed to Yes/No.
* Column names are conformed to snake_case (see ``config.COLUMN_RENAMES``).
* Whitespace is trimmed, duplicates on ``customer_id`` are removed (first wins).
* A binary ``churn_flag`` (1 = churned) is added for arithmetic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict

import pandas as pd

from . import config

log = logging.getLogger(__name__)


@dataclass
class CleaningReport:
    rows_in: int = 0
    rows_out: int = 0
    duplicates_removed: int = 0
    total_charges_blank: int = 0
    total_charges_imputed_zero: int = 0
    total_charges_unparseable: int = 0
    unknown_category_values: dict[str, list[str]] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _yes_no_from_binary(series: pd.Series) -> pd.Series:
    mapping = {"0": "No", "1": "Yes", "0.0": "No", "1.0": "Yes", "No": "No", "Yes": "Yes"}
    return series.astype(str).str.strip().map(mapping)


def clean_telco(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Return (clean_df, report). Never mutates the input."""
    report = CleaningReport(rows_in=len(df_raw))
    df = df_raw.copy()

    # 1. trim whitespace everywhere
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    # 2. conform column names
    df = df.rename(columns=config.COLUMN_RENAMES)

    # 3. de-duplicate on the business key
    before = len(df)
    df = df.drop_duplicates(subset="customer_id", keep="first")
    report.duplicates_removed = before - len(df)

    # 4. types
    df["tenure_months"] = pd.to_numeric(df["tenure_months"], errors="coerce").fillna(0).astype(int)
    df["monthly_charges"] = pd.to_numeric(df["monthly_charges"], errors="coerce")

    blank_mask = df["total_charges"].eq("")
    report.total_charges_blank = int(blank_mask.sum())
    total = pd.to_numeric(df["total_charges"], errors="coerce")
    report.total_charges_unparseable = int(total.isna().sum() - blank_mask.sum())
    impute_mask = total.isna() & df["tenure_months"].eq(0)
    report.total_charges_imputed_zero = int(impute_mask.sum())
    total = total.where(~impute_mask, 0.0)
    # anything still NaN (non-zero tenure but unparseable) → monthly * tenure estimate
    est = df["monthly_charges"] * df["tenure_months"]
    df["total_charges"] = total.fillna(est)

    df["senior_citizen"] = _yes_no_from_binary(df["senior_citizen"])

    # 5. churn flag
    df["churn_flag"] = (df["churn"] == "Yes").astype(int)

    # 6. domain audit (report only — the quality gate decides what to do)
    for col, allowed in config.CATEGORY_DOMAINS.items():
        bad = sorted(set(df[col].dropna().unique()) - allowed)
        if bad:
            report.unknown_category_values[col] = bad

    report.rows_out = len(df)
    log.info(
        "Cleaned %s -> %s rows | blanks in total_charges: %s (imputed 0: %s) | dupes: %s",
        report.rows_in, report.rows_out, report.total_charges_blank,
        report.total_charges_imputed_zero, report.duplicates_removed,
    )
    return df.reset_index(drop=True), report
