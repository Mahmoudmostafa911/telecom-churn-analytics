"""Star schema build + SQL layer.

The feature frame is decomposed into a small Kimball-style star:

    dim_customer  dim_contract  dim_services  dim_date
            \\         |            /            |
             fact_customer (1 row / customer)   fact_network_monthly (1 row / customer-month)

The same tables are written as CSV (for Power BI import / SQL Server BULK
INSERT) and loaded into a local SQLite database so that the portable analytics
queries in ``sql/analytics`` can be executed on any machine with Python only.
The T-SQL scripts in ``sql/sqlserver`` create the identical structure on
SQL Server, so the analytics queries run unchanged in SSMS.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from . import config

log = logging.getLogger(__name__)

CUSTOMER_DIM_COLS = ["customer_id", "gender", "senior_citizen", "partner", "dependents",
                     "tenure_months", "tenure_bucket"]
CONTRACT_DIM_COLS = ["contract", "paperless_billing", "payment_method", "is_auto_payment"]
SERVICES_DIM_COLS = ["phone_service", "multiple_lines", "internet_service", "online_security",
                     "online_backup", "device_protection", "tech_support", "streaming_tv",
                     "streaming_movies", "num_addon_services", "has_internet", "has_phone",
                     "has_streaming"]
FACT_MEASURE_COLS = ["monthly_charges", "total_charges", "lifetime_avg_monthly", "charge_ratio",
                     "revenue_band", "churn", "churn_flag",
                     "kpi_months", "avg_dropped_call_pct", "avg_download_mbps", "avg_latency_ms",
                     "total_outage_minutes", "avg_data_usage_gb", "network_complaints",
                     "l3m_dropped_call_pct", "l3m_download_mbps", "l3m_latency_ms",
                     "l3m_outage_minutes", "l3m_complaints", "dropped_call_trend_pp",
                     "latency_trend_pct", "download_trend_pct", "network_quality_score",
                     "network_quality_band", "churn_probability", "risk_band"]


def _surrogate_dim(df: pd.DataFrame, cols: list[str], key_name: str) -> pd.DataFrame:
    dim = df[cols].drop_duplicates().sort_values(cols).reset_index(drop=True)
    dim.insert(0, key_name, range(1, len(dim) + 1))
    return dim


def build_dim_date(months: list[str]) -> pd.DataFrame:
    months = sorted(set(months))
    rows = []
    for i, m in enumerate(months, start=1):
        year, mon = int(m[:4]), int(m[5:7])
        rows.append({
            "month_key": year * 100 + mon,
            "month": m,
            "year": year,
            "month_number": mon,
            "month_name": pd.Timestamp(year=year, month=mon, day=1).strftime("%b"),
            "quarter": f"Q{(mon - 1) // 3 + 1}",
            "month_start_date": f"{year:04d}-{mon:02d}-01",
            "month_index": i,
            "months_before_snapshot": len(months) - i,
        })
    return pd.DataFrame(rows)


def build_star_schema(features: pd.DataFrame, kpis: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    f = features.copy()
    for col in ["churn_probability", "risk_band"]:
        if col not in f.columns:
            f[col] = pd.NA
    for col in FACT_MEASURE_COLS:
        if col not in f.columns:
            f[col] = pd.NA

    dim_customer = _surrogate_dim(f, CUSTOMER_DIM_COLS, "customer_key")
    dim_contract = _surrogate_dim(f, CONTRACT_DIM_COLS, "contract_key")
    dim_services = _surrogate_dim(f, SERVICES_DIM_COLS, "services_key")

    fact = (f.merge(dim_customer[["customer_key", "customer_id"]], on="customer_id")
             .merge(dim_contract, on=CONTRACT_DIM_COLS)
             .merge(dim_services, on=SERVICES_DIM_COLS))
    fact_customer = fact[["customer_key", "contract_key", "services_key", "customer_id"]
                         + FACT_MEASURE_COLS].sort_values("customer_key").reset_index(drop=True)

    tables = {
        "dim_customer": dim_customer,
        "dim_contract": dim_contract,
        "dim_services": dim_services,
        "fact_customer": fact_customer,
    }

    if kpis is not None and not kpis.empty:
        dim_date = build_dim_date(kpis["month"].astype(str).tolist())
        fnm = (kpis.merge(dim_customer[["customer_key", "customer_id"]], on="customer_id", how="inner")
                   .merge(dim_date[["month_key", "month"]], on="month", how="inner"))
        fact_network_monthly = fnm[["customer_key", "month_key", "customer_id", "month", "month_index",
                                    "dropped_call_pct", "avg_download_mbps", "avg_latency_ms",
                                    "outage_minutes", "data_usage_gb", "complaints"]]
        tables["dim_date"] = dim_date
        tables["fact_network_monthly"] = fact_network_monthly.sort_values(
            ["customer_key", "month_key"]).reset_index(drop=True)

    log.info("Star schema: %s", {k: len(v) for k, v in tables.items()})
    return tables


def write_star_csvs(tables: dict[str, pd.DataFrame], out_dir: Path = config.STAR_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, df in tables.items():
        p = out_dir / f"{name}.csv"
        df.to_csv(p, index=False, lineterminator="\n")  # LF so BULK INSERT ROWTERMINATOR=0x0a works
        paths.append(p)
    log.info("Wrote %s star-schema CSVs to %s", len(paths), out_dir)
    return paths


def load_sqlite(tables: dict[str, pd.DataFrame], db_path: Path = config.DB_PATH) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        for name, df in tables.items():
            df.to_sql(name, conn, if_exists="replace", index=False)
        for name, key in [("dim_customer", "customer_key"), ("dim_contract", "contract_key"),
                          ("dim_services", "services_key"), ("fact_customer", "customer_key")]:
            if name in tables:
                conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{name}_{key} ON {name}({key})")
        if "fact_network_monthly" in tables:
            conn.execute("CREATE INDEX IF NOT EXISTS ix_fnm_customer ON fact_network_monthly(customer_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_fnm_month ON fact_network_monthly(month_key)")
    log.info("SQLite warehouse written to %s", db_path)
    return db_path


def run_analytics_sql(db_path: Path = config.DB_PATH,
                      sql_dir: Path = config.ANALYTICS_SQL_DIR,
                      out_dir: Path = config.ANALYTICS_DIR) -> dict[str, pd.DataFrame]:
    """Execute every ``sql/analytics/*.sql`` file against SQLite; save results as CSV."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, pd.DataFrame] = {}
    with sqlite3.connect(db_path) as conn:
        for sql_file in sorted(Path(sql_dir).glob("*.sql")):
            sql = sql_file.read_text(encoding="utf-8")
            df = pd.read_sql_query(sql, conn)
            name = sql_file.stem
            df.to_csv(out_dir / f"{name}.csv", index=False)
            results[name] = df
            log.info("Analytics %-40s -> %4d rows", name, len(df))
    return results
