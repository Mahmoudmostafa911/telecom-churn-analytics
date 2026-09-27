"""Ingestion: read raw files as strings and enforce the schema contract.

Reading everything as text first is deliberate — it lets the cleaning step
decide how to handle malformed values (e.g. the blank ``TotalCharges`` cells
in the IBM file) instead of letting pandas guess.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import config

log = logging.getLogger(__name__)


class SchemaError(ValueError):
    """Raised when a raw file does not match the expected column contract."""


def _check_columns(actual: list[str], expected: list[str], name: str) -> None:
    missing = [c for c in expected if c not in actual]
    extra = [c for c in actual if c not in expected]
    if missing:
        raise SchemaError(f"{name}: missing columns {missing}")
    if extra:
        log.warning("%s: unexpected extra columns ignored: %s", name, extra)


def load_raw_telco(path: str | Path = config.DEFAULT_RAW_FILE) -> pd.DataFrame:
    """Load the IBM Telco CSV (or the synthetic fixture) as raw strings."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Raw file not found: {path}\n"
            "Run `python data/download_data.py` (real data) or "
            "`python data/make_synthetic_fixture.py` (synthetic fixture)."
        )
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    _check_columns(list(df.columns), config.RAW_COLUMNS, path.name)
    df = df[config.RAW_COLUMNS]  # enforce order, drop extras
    log.info("Loaded %s rows x %s columns from %s", len(df), df.shape[1], path.name)
    return df


def load_network_kpis(path: str | Path = config.DEFAULT_KPI_FILE) -> pd.DataFrame:
    """Load the monthly network KPI file with typed columns."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"KPI file not found: {path}\nRun `python data/generate_network_kpis.py`."
        )
    df = pd.read_csv(path)
    _check_columns(list(df.columns), config.KPI_COLUMNS, path.name)
    df = df[config.KPI_COLUMNS].copy()
    df["customer_id"] = df["customer_id"].astype(str).str.strip()
    df["month"] = df["month"].astype(str)
    df["month_index"] = df["month_index"].astype(int)
    for col in ["dropped_call_pct", "avg_download_mbps", "avg_latency_ms",
                "outage_minutes", "data_usage_gb"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["complaints"] = pd.to_numeric(df["complaints"], errors="coerce").fillna(0).astype(int)
    log.info("Loaded %s KPI rows for %s customers", len(df), df["customer_id"].nunique())
    return df
