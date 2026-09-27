"""Quality gate: declarative rule checks that produce a ``dq_results`` table.

Design
------
* Every check is a small function returning a :class:`CheckResult`.
* Severity is decided by the *rule*, not by the caller: a broken business key
  is always FAIL, a soft expectation (row count, reconciliation) is WARN.
* ``run_quality_gate`` returns a tidy DataFrame (one row per check) that is
  persisted next to the data so every pipeline run leaves an audit trail.
* Any FAIL raises :class:`DataQualityError` unless ``fail_on_error=False``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from . import config

log = logging.getLogger(__name__)

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


class DataQualityError(RuntimeError):
    """Raised when at least one FAIL-severity check does not pass."""


@dataclass
class CheckResult:
    check_name: str
    table: str
    status: str
    observed: str
    expectation: str
    details: str = ""


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #
def check_row_count(df: pd.DataFrame, table: str, expected: int | None) -> CheckResult:
    n = len(df)
    if expected is None:
        return CheckResult("row_count", table, PASS, str(n), "> 0" if n else "> 0",
                           "no expected count configured")
    status = PASS if n == expected else WARN
    return CheckResult("row_count", table, status, str(n), f"== {expected}",
                       "" if status == PASS else "row count differs from the published dataset size")


def check_unique_key(df: pd.DataFrame, table: str, key: str | list[str]) -> CheckResult:
    keys = [key] if isinstance(key, str) else key
    dupes = int(df.duplicated(subset=keys).sum())
    return CheckResult(f"unique_{'_'.join(keys)}", table, PASS if dupes == 0 else FAIL,
                       f"{dupes} duplicates", "0 duplicates")


def check_not_null(df: pd.DataFrame, table: str, cols: list[str]) -> list[CheckResult]:
    out = []
    for c in cols:
        nulls = int(df[c].isna().sum()) if c in df.columns else len(df)
        out.append(CheckResult(f"not_null_{c}", table, PASS if nulls == 0 else FAIL,
                               f"{nulls} nulls", "0 nulls"))
    return out


def check_domain(df: pd.DataFrame, table: str, col: str, allowed: set[str]) -> CheckResult:
    bad = sorted(set(df[col].dropna().astype(str).unique()) - allowed)
    return CheckResult(f"domain_{col}", table, PASS if not bad else FAIL,
                       f"{len(bad)} unknown values", f"subset of {sorted(allowed)}",
                       ", ".join(bad[:10]))


def check_range(df: pd.DataFrame, table: str, col: str, lo: float, hi: float,
                severity: str = FAIL) -> CheckResult:
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    out_of_range = int(((s < lo) | (s > hi)).sum())
    return CheckResult(f"range_{col}", table, PASS if out_of_range == 0 else severity,
                       f"{out_of_range} outside", f"[{lo}, {hi}]")


def check_referential(child: pd.DataFrame, parent: pd.DataFrame, table: str, key: str) -> CheckResult:
    orphans = int((~child[key].isin(parent[key])).sum())
    return CheckResult(f"fk_{key}_exists", table, PASS if orphans == 0 else FAIL,
                       f"{orphans} orphan rows", "0 orphans",
                       "every KPI row must belong to a known customer")


def check_charges_reconcile(df: pd.DataFrame, table: str, tolerance: float = 0.5,
                            max_share: float = 0.05) -> CheckResult:
    """total_charges should be roughly monthly_charges x tenure (WARN if many outliers)."""
    billed = df[df["tenure_months"] > 0]
    expected = billed["monthly_charges"] * billed["tenure_months"]
    deviation = ((billed["total_charges"] - expected).abs() / expected.replace(0, pd.NA)).astype(float)
    share = float((deviation > tolerance).mean()) if len(billed) else 0.0
    return CheckResult("reconcile_total_vs_monthly_x_tenure", table,
                       PASS if share <= max_share else WARN,
                       f"{share:.1%} rows deviate > {tolerance:.0%}", f"<= {max_share:.0%} rows",
                       "large deviations usually mean plan changes, not bad data")


def check_churn_rate_plausible(df: pd.DataFrame, table: str, lo=0.10, hi=0.45) -> CheckResult:
    rate = float(df["churn_flag"].mean()) if len(df) else 0.0
    return CheckResult("churn_rate_plausible", table, PASS if lo <= rate <= hi else WARN,
                       f"{rate:.1%}", f"between {lo:.0%} and {hi:.0%}")


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_quality_gate(customers: pd.DataFrame, kpis: pd.DataFrame | None,
                     expected_rows: int | None = None,
                     fail_on_error: bool = True) -> pd.DataFrame:
    """Run every check and return the dq_results table."""
    results: list[CheckResult] = []
    t = "customers"
    results.append(check_row_count(customers, t, expected_rows))
    results.append(check_unique_key(customers, t, "customer_id"))
    results += check_not_null(customers, t, ["customer_id", "tenure_months", "monthly_charges",
                                              "total_charges", "churn_flag", "contract"])
    for col, allowed in config.CATEGORY_DOMAINS.items():
        results.append(check_domain(customers, t, col, allowed))
    for col in ["tenure_months", "monthly_charges", "total_charges"]:
        lo, hi = config.NUMERIC_RANGES[col]
        results.append(check_range(customers, t, col, lo, hi))
    results.append(check_range(customers, t, "churn_flag", 0, 1))
    results.append(check_charges_reconcile(customers, t))
    results.append(check_churn_rate_plausible(customers, t))

    if kpis is not None and not kpis.empty:
        k = "network_kpis_monthly"
        results.append(check_unique_key(kpis, k, ["customer_id", "month"]))
        results += check_not_null(kpis, k, ["customer_id", "month", "month_index"])
        results.append(check_referential(kpis, customers, k, "customer_id"))
        results.append(check_range(kpis, k, "month_index", 1, config.OBSERVATION_MONTHS))
        for col in ["dropped_call_pct", "avg_download_mbps", "avg_latency_ms",
                    "outage_minutes", "data_usage_gb", "complaints"]:
            lo, hi = config.NUMERIC_RANGES[col]
            results.append(check_range(kpis, k, col, lo, hi, severity=WARN))

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dq = pd.DataFrame([asdict(r) for r in results])
    dq.insert(0, "run_ts", run_ts)

    summary = dq["status"].value_counts().to_dict()
    log.info("Quality gate: %s", summary)
    failures = dq[dq["status"] == FAIL]
    if not failures.empty:
        msg = "; ".join(f"{r.check_name} ({r.observed})" for r in failures.itertuples())
        if fail_on_error:
            raise DataQualityError(f"{len(failures)} check(s) FAILED: {msg}")
        log.error("Quality gate FAILED (continuing because fail_on_error=False): %s", msg)
    return dq
