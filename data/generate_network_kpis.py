"""Generate SYNTHETIC monthly network-quality telemetry for every customer.

The IBM dataset has no operational data, yet in a real telco the most
interesting churn question is "does the network experience explain it?".
This script fabricates a plausible telemetry table so the project can show
*how* such data is joined, aggregated and modelled:

* one row per customer per month for the 12 months before the snapshot
  (a customer with tenure 4 only has 4 rows);
* KPIs depend on the access technology (fiber is faster / lower latency
  than DSL; phone-only customers have no internet KPIs);
* each customer has a persistent "network luck" factor;
* **churners are given a mild degradation in the last three months** — this
  pattern is BUILT IN, so any analysis of it demonstrates technique, not a
  real-world finding. README and findings.md repeat this warning.

Usage:
    python data/generate_network_kpis.py                       # uses data/raw/Telco-Customer-Churn.csv
    python data/generate_network_kpis.py --customers data/raw/telco_synthetic_fixture.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from telco_churn import config  # noqa: E402


def _months(snapshot: str, n: int) -> list[str]:
    end = pd.Period(snapshot, freq="M")
    return [str(end - (n - i)) for i in range(1, n + 1)]  # oldest -> newest


def generate(customers: pd.DataFrame, seed: int = config.SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    months = _months(config.SNAPSHOT_MONTH, config.OBSERVATION_MONTHS)
    n_months = len(months)

    cid = customers["customerID"].astype(str).str.strip().to_numpy()
    tenure = pd.to_numeric(customers["tenure"], errors="coerce").fillna(0).astype(int).to_numpy()
    churned = (customers["Churn"].astype(str).str.strip() == "Yes").to_numpy()
    internet = customers["InternetService"].astype(str).str.strip().to_numpy()
    phone = (customers["PhoneService"].astype(str).str.strip() == "Yes").to_numpy()
    streaming = ((customers["StreamingTV"].astype(str).str.strip() == "Yes")
                 | (customers["StreamingMovies"].astype(str).str.strip() == "Yes")).to_numpy()

    fiber, dsl, no_net = internet == "Fiber optic", internet == "DSL", internet == "No"
    luck = rng.lognormal(0.0, 0.25, len(cid))            # persistent per-customer quality factor
    active_months = np.clip(np.maximum(tenure, 1), 1, n_months)

    rows = []
    for i in range(len(cid)):
        first_idx = n_months - active_months[i] + 1      # month_index runs 1..12, 12 = newest
        for m_idx in range(first_idx, n_months + 1):
            recency = max(0, m_idx - (n_months - 3))       # 1,2,3 for the last three months
            degrade = 1.0 + (0.25 * recency if churned[i] else 0.0)

            dropped = rng.gamma(2.0, 0.35) * luck[i] * (1.3 if churned[i] else 1.0) * degrade if phone[i] else np.nan
            if fiber[i]:
                speed, latency, outage_l, usage = rng.normal(190, 35), rng.normal(18, 4) * luck[i], 10, rng.normal(260, 80)
            elif dsl[i]:
                speed, latency, outage_l, usage = rng.normal(25, 6), rng.normal(42, 9) * luck[i], 18, rng.normal(95, 30)
            else:
                speed, latency, outage_l, usage = np.nan, np.nan, 5, np.nan
            if not no_net[i]:
                speed = speed * (1 - 0.06 * recency if churned[i] else 1.0)
                latency = latency * degrade
                usage = usage + (60 if fiber[i] and streaming[i] else 40 if streaming[i] else 0)
            outage = rng.poisson(outage_l * luck[i] * (2.0 if (churned[i] and recency) else 1.0))
            complaints = rng.poisson(0.25 if (churned[i] and recency) else 0.04)

            rows.append((cid[i], months[m_idx - 1], m_idx,
                         None if np.isnan(dropped) else round(float(max(dropped, 0)), 3),
                         None if np.isnan(speed) else round(float(max(speed, 1)), 1),
                         None if np.isnan(latency) else round(float(max(latency, 3)), 1),
                         int(outage),
                         None if np.isnan(usage) else round(float(max(usage, 1)), 1),
                         int(complaints)))

    return pd.DataFrame(rows, columns=config.KPI_COLUMNS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--customers", type=Path, default=config.DEFAULT_RAW_FILE,
                    help="raw Telco CSV (real or fixture) that supplies the customer list")
    ap.add_argument("--out", type=Path, default=config.DEFAULT_KPI_FILE)
    ap.add_argument("--seed", type=int, default=config.SEED)
    args = ap.parse_args()

    if not args.customers.exists():
        print(f"Customer file not found: {args.customers}. Run download_data.py or make_synthetic_fixture.py first.")
        return 1
    customers = pd.read_csv(args.customers, dtype=str, keep_default_na=False)
    kpis = generate(customers, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    kpis.to_csv(args.out, index=False)
    print(f"Wrote {len(kpis):,} customer-month rows for {kpis['customer_id'].nunique():,} customers -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
