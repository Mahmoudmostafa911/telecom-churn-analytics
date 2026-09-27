"""Central configuration: paths, schema contracts and business constants.

Everything that a second engineer would need to change lives here, so the
transformation code stays free of magic strings.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths (resolved relative to the repository root, wherever it is cloned)
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
STAR_DIR = PROCESSED_DIR / "star"            # CSV extracts of the star schema (Power BI import)
ANALYTICS_DIR = PROCESSED_DIR / "analytics"  # results of sql/analytics/*.sql
SQL_DIR = PROJECT_ROOT / "sql"
ANALYTICS_SQL_DIR = SQL_DIR / "analytics"
MODEL_DIR = PROJECT_ROOT / "model"
DOCS_DIR = PROJECT_ROOT / "docs"
IMG_DIR = DOCS_DIR / "img"
DB_PATH = PROCESSED_DIR / "telco_churn.sqlite"

DEFAULT_RAW_FILE = RAW_DIR / "Telco-Customer-Churn.csv"
FIXTURE_RAW_FILE = RAW_DIR / "telco_synthetic_fixture.csv"
DEFAULT_KPI_FILE = RAW_DIR / "network_kpis_monthly.csv"

# Public source of the real dataset (IBM sample data, Apache-2.0 licensed repo)
TELCO_SOURCE_URL = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "master/data/Telco-Customer-Churn.csv"
)
EXPECTED_REAL_ROWS = 7043

SEED = 42

# --------------------------------------------------------------------------- #
# Schema contract for the raw IBM file (exact header, in order)
# --------------------------------------------------------------------------- #
RAW_COLUMNS = [
    "customerID", "gender", "SeniorCitizen", "Partner", "Dependents", "tenure",
    "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity",
    "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
    "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod",
    "MonthlyCharges", "TotalCharges", "Churn",
]

# raw name -> conformed snake_case name
COLUMN_RENAMES = {
    "customerID": "customer_id",
    "gender": "gender",
    "SeniorCitizen": "senior_citizen",
    "Partner": "partner",
    "Dependents": "dependents",
    "tenure": "tenure_months",
    "PhoneService": "phone_service",
    "MultipleLines": "multiple_lines",
    "InternetService": "internet_service",
    "OnlineSecurity": "online_security",
    "OnlineBackup": "online_backup",
    "DeviceProtection": "device_protection",
    "TechSupport": "tech_support",
    "StreamingTV": "streaming_tv",
    "StreamingMovies": "streaming_movies",
    "Contract": "contract",
    "PaperlessBilling": "paperless_billing",
    "PaymentMethod": "payment_method",
    "MonthlyCharges": "monthly_charges",
    "TotalCharges": "total_charges",
    "Churn": "churn",
}

ADDON_SERVICES = [
    "online_security", "online_backup", "device_protection",
    "tech_support", "streaming_tv", "streaming_movies",
]

# Allowed values per categorical column (after renaming). Anything outside
# these domains is reported by the quality gate.
CATEGORY_DOMAINS = {
    "gender": {"Female", "Male"},
    "senior_citizen": {"Yes", "No"},
    "partner": {"Yes", "No"},
    "dependents": {"Yes", "No"},
    "phone_service": {"Yes", "No"},
    "multiple_lines": {"Yes", "No", "No phone service"},
    "internet_service": {"DSL", "Fiber optic", "No"},
    "online_security": {"Yes", "No", "No internet service"},
    "online_backup": {"Yes", "No", "No internet service"},
    "device_protection": {"Yes", "No", "No internet service"},
    "tech_support": {"Yes", "No", "No internet service"},
    "streaming_tv": {"Yes", "No", "No internet service"},
    "streaming_movies": {"Yes", "No", "No internet service"},
    "contract": {"Month-to-month", "One year", "Two year"},
    "paperless_billing": {"Yes", "No"},
    "payment_method": {
        "Electronic check", "Mailed check",
        "Bank transfer (automatic)", "Credit card (automatic)",
    },
    "churn": {"Yes", "No"},
}

# --------------------------------------------------------------------------- #
# Network KPI file contract (synthetic telemetry, one row per customer-month)
# --------------------------------------------------------------------------- #
KPI_COLUMNS = [
    "customer_id", "month", "month_index", "dropped_call_pct",
    "avg_download_mbps", "avg_latency_ms", "outage_minutes",
    "data_usage_gb", "complaints",
]
OBSERVATION_MONTHS = 12          # telemetry window: the 12 months before the snapshot
SNAPSHOT_MONTH = "2025-12"       # last month in the window

# --------------------------------------------------------------------------- #
# Business rules
# --------------------------------------------------------------------------- #
TENURE_BUCKETS = [(0, 12, "00-12 months"), (13, 24, "13-24 months"),
                  (25, 48, "25-48 months"), (49, 72, "49-72 months")]

RISK_BANDS = [(0.00, 0.20, "Low"), (0.20, 0.50, "Medium"), (0.50, 1.01, "High")]

# Numeric sanity ranges used by the quality gate
NUMERIC_RANGES = {
    "tenure_months": (0, 72),
    "monthly_charges": (0, 200),
    "total_charges": (0, 15000),
    "dropped_call_pct": (0, 100),
    "avg_download_mbps": (0, 2000),
    "avg_latency_ms": (0, 1000),
    "outage_minutes": (0, 44640),
    "data_usage_gb": (0, 5000),
    "complaints": (0, 100),
}
