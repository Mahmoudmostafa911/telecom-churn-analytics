"""Feature engineering: customer attributes + aggregated network telemetry.

Two families of features are produced:

1. **Customer / billing features** derived from the IBM file only
   (tenure bucket, number of add-on services, ARPU-style ratios, auto-pay flag).
2. **Network features** aggregated from the monthly KPI file
   (12-month averages, last-3-month averages and the *trend* between them,
   plus a 0–100 ``network_quality_score`` composite).

All functions are pure: they take DataFrames and return new DataFrames.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Customer features
# --------------------------------------------------------------------------- #
def tenure_bucket(months: int) -> str:
    for lo, hi, label in config.TENURE_BUCKETS:
        if lo <= months <= hi:
            return label
    return config.TENURE_BUCKETS[-1][2] if months > 72 else config.TENURE_BUCKETS[0][2]


def add_customer_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["tenure_bucket"] = out["tenure_months"].apply(tenure_bucket)
    out["num_addon_services"] = sum((out[c] == "Yes").astype(int) for c in config.ADDON_SERVICES)
    out["has_internet"] = (out["internet_service"] != "No").astype(int)
    out["has_phone"] = (out["phone_service"] == "Yes").astype(int)
    out["has_streaming"] = ((out["streaming_tv"] == "Yes") | (out["streaming_movies"] == "Yes")).astype(int)
    out["is_auto_payment"] = out["payment_method"].str.contains("automatic", case=False).astype(int)
    out["is_month_to_month"] = (out["contract"] == "Month-to-month").astype(int)

    # Average monthly spend over the lifetime vs. the current bill. A ratio > 1
    # means the customer is paying more now than they historically did.
    lifetime_avg = np.where(out["tenure_months"] > 0,
                            out["total_charges"] / out["tenure_months"].replace(0, np.nan),
                            out["monthly_charges"])
    out["lifetime_avg_monthly"] = np.round(lifetime_avg, 2)
    out["charge_ratio"] = np.round(out["monthly_charges"] / out["lifetime_avg_monthly"].replace(0, np.nan), 3)
    out["charge_ratio"] = out["charge_ratio"].fillna(1.0)

    # Revenue band by quartile of monthly charges (labels are stable business terms)
    try:
        out["revenue_band"] = pd.qcut(out["monthly_charges"], 4,
                                      labels=["Low", "Mid", "High", "Premium"]).astype(str)
    except ValueError:  # tiny frames in tests
        out["revenue_band"] = "Mid"
    return out


# --------------------------------------------------------------------------- #
# Network features
# --------------------------------------------------------------------------- #
def _score(series: pd.Series, lo: float, hi: float, higher_is_better: bool) -> pd.Series:
    """Min-max scale a KPI into 0..1 using fixed business bounds (not data bounds)."""
    s = ((series - lo) / (hi - lo)).clip(0, 1)
    return s if higher_is_better else 1 - s


def aggregate_network_kpis(kpis: pd.DataFrame) -> pd.DataFrame:
    """One row per customer with 12-month and last-3-month network aggregates."""
    k = kpis.copy()
    last3 = k[k["month_index"] > config.OBSERVATION_MONTHS - 3]

    agg_all = k.groupby("customer_id").agg(
        kpi_months=("month_index", "count"),
        avg_dropped_call_pct=("dropped_call_pct", "mean"),
        avg_download_mbps=("avg_download_mbps", "mean"),
        avg_latency_ms=("avg_latency_ms", "mean"),
        total_outage_minutes=("outage_minutes", "sum"),
        avg_data_usage_gb=("data_usage_gb", "mean"),
        network_complaints=("complaints", "sum"),
    )
    agg_l3 = last3.groupby("customer_id").agg(
        l3m_dropped_call_pct=("dropped_call_pct", "mean"),
        l3m_download_mbps=("avg_download_mbps", "mean"),
        l3m_latency_ms=("avg_latency_ms", "mean"),
        l3m_outage_minutes=("outage_minutes", "sum"),
        l3m_complaints=("complaints", "sum"),
    )
    agg = agg_all.join(agg_l3, how="left")

    # Trend = recent vs. whole-window (positive = getting worse for "bad" KPIs)
    agg["dropped_call_trend_pp"] = (agg["l3m_dropped_call_pct"] - agg["avg_dropped_call_pct"]).round(3)
    agg["latency_trend_pct"] = ((agg["l3m_latency_ms"] / agg["avg_latency_ms"].replace(0, np.nan) - 1) * 100).round(1)
    agg["download_trend_pct"] = ((agg["l3m_download_mbps"] / agg["avg_download_mbps"].replace(0, np.nan) - 1) * 100).round(1)

    for col in ["avg_dropped_call_pct", "avg_download_mbps", "avg_latency_ms",
                "avg_data_usage_gb", "l3m_dropped_call_pct", "l3m_download_mbps", "l3m_latency_ms"]:
        agg[col] = agg[col].round(2)
    return agg.reset_index()


def add_quality_score(df: pd.DataFrame) -> pd.DataFrame:
    """Composite 0-100 network quality score, *relative to the access technology*.

    Fiber is inherently faster and lower-latency than DSL, so comparing raw
    Mbps across technologies would just re-discover "who has fiber" (and fiber
    customers churn more for pricing reasons — a classic confounder). Speed and
    latency are therefore expressed as a ratio to the median of the customer's
    own technology; drops, outages and complaints use fixed business bounds.
    Components a customer does not have (no internet → no speed) are skipped.
    """
    out = df.copy()
    tech = out["internet_service"] if "internet_service" in out.columns else pd.Series("All", index=out.index)
    med_latency = out.groupby(tech)["avg_latency_ms"].transform("median")
    med_speed = out.groupby(tech)["avg_download_mbps"].transform("median")
    latency_ratio = out["avg_latency_ms"] / med_latency.replace(0, np.nan)     # 1.0 = typical, 2.0 = twice as slow
    speed_ratio = out["avg_download_mbps"] / med_speed.replace(0, np.nan)      # 1.0 = typical, 0.5 = half speed

    components = pd.concat([
        _score(out["avg_dropped_call_pct"], 0.0, 3.0, higher_is_better=False),
        _score(latency_ratio, 0.6, 2.0, higher_is_better=False),
        _score(speed_ratio, 0.5, 1.2, higher_is_better=True),
        _score(out["total_outage_minutes"], 0.0, 400.0, higher_is_better=False),
        _score(out["network_complaints"], 0.0, 4.0, higher_is_better=False),
    ], axis=1)
    out["network_quality_score"] = (components.mean(axis=1, skipna=True) * 100).round(1)
    out["network_quality_band"] = pd.cut(
        out["network_quality_score"], bins=[-0.1, 55, 70, 82, 100.1],
        labels=["Poor", "Fair", "Good", "Excellent"]).astype(str)
    out.loc[out["kpi_months"].fillna(0) == 0, ["network_quality_score", "network_quality_band"]] = [np.nan, "No telemetry"]
    return out


def add_network_features(customers: pd.DataFrame, kpis: pd.DataFrame | None) -> pd.DataFrame:
    """Left-join aggregated telemetry onto the customer frame."""
    if kpis is None or kpis.empty:
        log.warning("No network KPIs supplied — network features skipped")
        return customers.copy()
    agg = aggregate_network_kpis(kpis)
    out = customers.merge(agg, on="customer_id", how="left")
    matched = out["kpi_months"].notna().mean() * 100
    log.info("Network features joined for %.1f%% of customers", matched)
    out["kpi_months"] = out["kpi_months"].fillna(0).astype(int)
    out["network_complaints"] = out["network_complaints"].fillna(0).astype(int)
    out = add_quality_score(out)
    return out


def build_features(customers_clean: pd.DataFrame, kpis: pd.DataFrame | None) -> pd.DataFrame:
    """Full feature frame = customer features + network features."""
    return add_network_features(add_customer_features(customers_clean), kpis)
