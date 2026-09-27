"""Small in-memory fixtures shared by the tests (unittest + pytest compatible)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data"))

from telco_churn import config  # noqa: E402


def raw_frame(rows: list[dict] | None = None) -> pd.DataFrame:
    """A tiny raw Telco frame with the real header and formatting quirks."""
    base = {
        "customerID": "0001-AAAAA", "gender": "Female", "SeniorCitizen": "0", "Partner": "Yes",
        "Dependents": "No", "tenure": "12", "PhoneService": "Yes", "MultipleLines": "No",
        "InternetService": "Fiber optic", "OnlineSecurity": "No", "OnlineBackup": "Yes",
        "DeviceProtection": "No", "TechSupport": "No", "StreamingTV": "Yes", "StreamingMovies": "No",
        "Contract": "Month-to-month", "PaperlessBilling": "Yes", "PaymentMethod": "Electronic check",
        "MonthlyCharges": "89.1", "TotalCharges": "1069.2", "Churn": "Yes",
    }
    rows = rows or [
        {},
        {"customerID": "0002-BBBBB", "tenure": "0", "TotalCharges": " ", "Churn": "No",
         "Contract": "Two year", "SeniorCitizen": "1"},
        {"customerID": "0003-CCCCC", "tenure": "60", "TotalCharges": "5400", "MonthlyCharges": "90",
         "Churn": "No", "Contract": "One year", "InternetService": "No", "OnlineSecurity": "No internet service",
         "OnlineBackup": "No internet service", "DeviceProtection": "No internet service",
         "TechSupport": "No internet service", "StreamingTV": "No internet service",
         "StreamingMovies": "No internet service", "PaymentMethod": "Credit card (automatic)"},
    ]
    return pd.DataFrame([{**base, **r} for r in rows], columns=config.RAW_COLUMNS)


def kpi_frame(customer_ids: list[str], months: int = 12) -> pd.DataFrame:
    rows = []
    for cid in customer_ids:
        for i in range(1, months + 1):
            rows.append({"customer_id": cid, "month": f"2025-{i:02d}", "month_index": i,
                         "dropped_call_pct": 0.5 + 0.1 * i, "avg_download_mbps": 150.0,
                         "avg_latency_ms": 20.0 + i, "outage_minutes": 5, "data_usage_gb": 200.0,
                         "complaints": 1 if i == months else 0})
    return pd.DataFrame(rows, columns=config.KPI_COLUMNS)
