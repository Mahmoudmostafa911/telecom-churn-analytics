"""Create a SYNTHETIC stand-in for the IBM Telco file with the identical schema.

Why this exists
---------------
* CI runners and reviewers should be able to execute the whole pipeline
  without downloading anything.
* Unit tests need a deterministic dataset with known quirks (blank
  ``TotalCharges`` for tenure-0 customers, 0/1 ``SeniorCitizen``, etc.).

The generator reproduces the *shape* of the real data (7,043 rows, the same
categories, similar marginal distributions and the well-known churn drivers)
but every row is invented. Never quote numbers computed on this file as
findings — ``docs/findings.md`` carries a banner when it was built from it.

Usage:
    python data/make_synthetic_fixture.py            # -> data/raw/telco_synthetic_fixture.csv
    python data/make_synthetic_fixture.py --rows 500 --out tests/fixtures/small.csv
"""
from __future__ import annotations

import argparse
import string
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from telco_churn import config  # noqa: E402

TARGET_CHURN_RATE = 0.265


def _fmt_money(x: float) -> str:
    """Match the real file's formatting: 29.85, 1889.5, 97 (no trailing zeros)."""
    return f"{x:.2f}".rstrip("0").rstrip(".")


def generate(n_rows: int = 7043, seed: int = config.SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = n_rows

    # ids: 4 digits + '-' + 5 upper-case letters (unique)
    ids = set()
    while len(ids) < n:
        num = rng.integers(0, 10000)
        letters = "".join(rng.choice(list(string.ascii_uppercase), 5))
        ids.add(f"{num:04d}-{letters}")
    customer_id = np.array(sorted(ids))
    rng.shuffle(customer_id)

    gender = rng.choice(["Female", "Male"], n)
    senior = (rng.random(n) < 0.162).astype(int)
    partner = np.where(rng.random(n) < 0.483, "Yes", "No")
    dependents = np.where((partner == "Yes") & (rng.random(n) < 0.5) | (partner == "No") & (rng.random(n) < 0.12),
                          "Yes", "No")

    contract = rng.choice(["Month-to-month", "One year", "Two year"], n, p=[0.55, 0.21, 0.24])

    # tenure depends on contract; exactly 11 tenure-0 customers as in the IBM file
    tenure = np.empty(n, dtype=int)
    m2m = contract == "Month-to-month"
    one = contract == "One year"
    two = contract == "Two year"
    tenure[m2m] = np.clip(rng.geometric(1 / 16, m2m.sum()), 1, 72)
    tenure[one] = rng.integers(6, 73, one.sum())
    tenure[two] = np.clip(72 - rng.geometric(1 / 20, two.sum()) + 1, 1, 72)
    tenure[rng.choice(n, 11, replace=False)] = 0

    phone = np.where(rng.random(n) < 0.903, "Yes", "No")
    multiple = np.where(phone == "No", "No phone service", np.where(rng.random(n) < 0.47, "Yes", "No"))

    internet = rng.choice(["DSL", "Fiber optic", "No"], n, p=[0.34, 0.44, 0.22])
    has_net = internet != "No"

    def addon(p_dsl: float, p_fiber: float) -> np.ndarray:
        p = np.where(internet == "DSL", p_dsl, p_fiber)
        return np.where(~has_net, "No internet service", np.where(rng.random(n) < p, "Yes", "No"))

    online_security = addon(0.45, 0.30)
    online_backup = addon(0.46, 0.43)
    device_protection = addon(0.44, 0.44)
    tech_support = addon(0.46, 0.30)
    streaming_tv = addon(0.40, 0.56)
    streaming_movies = addon(0.41, 0.57)

    paperless = np.where(rng.random(n) < 0.592, "Yes", "No")

    payment = np.empty(n, dtype=object)
    methods = ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"]
    payment[m2m] = rng.choice(methods, m2m.sum(), p=[0.45, 0.25, 0.15, 0.15])
    payment[~m2m] = rng.choice(methods, (~m2m).sum(), p=[0.20, 0.20, 0.30, 0.30])

    # monthly charges built up from the service mix
    monthly = np.zeros(n)
    monthly += np.where(phone == "Yes", 19.5, 0.0) + np.where(multiple == "Yes", 5.0, 0.0)
    monthly += np.where(internet == "DSL", 25.0, np.where(internet == "Fiber optic", 50.0, 0.0))
    for arr in (online_security, online_backup, device_protection, tech_support):
        monthly += np.where(arr == "Yes", 5.0, 0.0)
    for arr in (streaming_tv, streaming_movies):
        monthly += np.where(arr == "Yes", 10.0, 0.0)
    monthly += rng.normal(0, 2.0, n)
    monthly = np.clip(np.round(monthly, 2), 18.25, 118.75)

    total = np.round(monthly * tenure * rng.uniform(0.92, 1.08, n), 2)

    # churn: logistic model with the well-known drivers, intercept calibrated to the target rate
    logit = (1.55 * m2m - 0.95 * two
             + 1.05 * (internet == "Fiber optic") - 1.00 * (~has_net)
             + 0.75 * (payment == "Electronic check")
             + 0.80 * senior + 0.35 * (paperless == "Yes")
             - 0.55 * (tech_support == "Yes") - 0.45 * (online_security == "Yes")
             - 0.25 * (partner == "Yes") - 0.30 * (dependents == "Yes")
             - 0.045 * tenure + 0.008 * (monthly - 65))
    lo, hi = -6.0, 6.0
    for _ in range(60):  # bisection on the intercept
        mid = (lo + hi) / 2
        rate = (1 / (1 + np.exp(-(logit + mid)))).mean()
        lo, hi = (mid, hi) if rate < TARGET_CHURN_RATE else (lo, mid)
    p_churn = 1 / (1 + np.exp(-(logit + (lo + hi) / 2)))
    churn = np.where(rng.random(n) < p_churn, "Yes", "No")

    df = pd.DataFrame({
        "customerID": customer_id, "gender": gender, "SeniorCitizen": senior, "Partner": partner,
        "Dependents": dependents, "tenure": tenure, "PhoneService": phone, "MultipleLines": multiple,
        "InternetService": internet, "OnlineSecurity": online_security, "OnlineBackup": online_backup,
        "DeviceProtection": device_protection, "TechSupport": tech_support, "StreamingTV": streaming_tv,
        "StreamingMovies": streaming_movies, "Contract": contract, "PaperlessBilling": paperless,
        "PaymentMethod": payment, "MonthlyCharges": [_fmt_money(x) for x in monthly],
        "TotalCharges": [" " if t == 0 else _fmt_money(x) for t, x in zip(tenure, total)],
        "Churn": churn,
    })
    return df[config.RAW_COLUMNS]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=int, default=7043)
    ap.add_argument("--seed", type=int, default=config.SEED)
    ap.add_argument("--out", type=Path, default=config.FIXTURE_RAW_FILE)
    args = ap.parse_args()

    df = generate(args.rows, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    churn_rate = (df["Churn"] == "Yes").mean()
    print(f"Wrote {len(df):,} synthetic rows to {args.out} | churn rate {churn_rate:.1%} | "
          f"blank TotalCharges: {(df['TotalCharges'] == ' ').sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
