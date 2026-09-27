"""Generate docs/findings.md from the artefacts of a pipeline run.

The document is regenerated on every run so numbers never go stale. A banner
states which source file produced the figures (real IBM data vs. the
synthetic fixture) so nobody quotes fixture numbers by accident.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config

log = logging.getLogger(__name__)


def _md_table(df: pd.DataFrame, max_rows: int = 25) -> str:
    d = df.head(max_rows)
    cols = list(d.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in d.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                cells.append(f"{v:,.2f}" if abs(v) < 1e6 else f"{v:,.0f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_findings(analytics: dict[str, pd.DataFrame], runs: dict, cleaning: dict, dq: pd.DataFrame,
                   source_file: Path, n_customers: int, is_fixture: bool,
                   out_path: Path = config.DOCS_DIR / "findings.md") -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    banner = (
        "> ⚠️ **Generated from the SYNTHETIC TEST FIXTURE** (`{f}`). These numbers only prove the "
        "pipeline runs; they are *not* findings about real customers. Re-run on the IBM file to "
        "replace this document.".format(f=source_file.name)
        if is_fixture else
        "> ✅ Generated from the **IBM Telco Customer Churn** dataset (`{f}`, {n:,} customers). "
        "Network telemetry sections use synthetic data — see the note in each section.".format(
            f=source_file.name, n=n_customers)
    )
    parts = [f"# Findings — Telecom Churn & Network Quality Analytics\n\n_Generated {ts} by "
             f"`telco_churn.pipeline`._\n\n{banner}\n"]

    # Headline numbers
    contract = analytics.get("01_churn_by_contract")
    if contract is not None and len(contract):
        total_cust = int(contract["customers"].sum())
        total_churn = int(contract["churned"].sum())
        rate = 100 * total_churn / total_cust
        lost = float(contract["monthly_revenue_lost"].sum())
        parts.append("## Headline numbers\n")
        parts.append(f"* **{total_cust:,} customers**, **{total_churn:,} churned** → overall churn rate "
                     f"**{rate:.1f}%**.")
        parts.append(f"* Churned customers represented **${lost:,.0f} of monthly recurring revenue**.")
        top = contract.iloc[0]
        low = contract.iloc[-1]
        parts.append(f"* Contract type is the sharpest split: **{top['contract']} {top['churn_rate_pct']:.1f}%** "
                     f"vs **{low['contract']} {low['churn_rate_pct']:.1f}%**.\n")

    # Cleaning + DQ
    parts.append("## Data quality\n")
    parts.append(f"* Rows in → out: {cleaning.get('rows_in')} → {cleaning.get('rows_out')} "
                 f"(duplicates removed: {cleaning.get('duplicates_removed')}).")
    parts.append(f"* `TotalCharges` blank cells: **{cleaning.get('total_charges_blank')}** — all belong to "
                 f"tenure-0 customers and were imputed as 0.0 ({cleaning.get('total_charges_imputed_zero')}).")
    if cleaning.get("unknown_category_values"):
        parts.append(f"* Unknown category values: `{cleaning['unknown_category_values']}`")
    counts = dq["status"].value_counts().to_dict()
    parts.append(f"* Quality gate: **{counts.get('PASS', 0)} PASS / {counts.get('WARN', 0)} WARN / "
                 f"{counts.get('FAIL', 0)} FAIL** across {len(dq)} checks "
                 f"(full log: `data/processed/dq_results.csv`).")
    warns = dq[dq["status"] != "PASS"]
    if len(warns):
        parts.append("\n" + _md_table(warns[["check_name", "table", "status", "observed", "expectation"]]))
    parts.append("")

    sections = [
        ("01_churn_by_contract", "Churn by contract type", "![](img/churn_by_contract.png)"),
        ("02_churn_by_internet_and_payment", "Churn by internet service × payment method",
         "![](img/churn_heatmap_internet_payment.png)"),
        ("03_tenure_curve", "Tenure curve (first 12 months shown)", "![](img/tenure_curve.png)"),
        ("04_addon_services_effect", "Add-on services and tech support (internet customers)", ""),
        ("06_revenue_at_risk_by_decile", "Revenue at risk by monthly-charge decile", ""),
        ("05_network_quality_vs_churn", "Network quality vs churn — ⚠️ synthetic telemetry",
         "![](img/network_quality_vs_churn.png)"),
        ("07_network_trend_churned_vs_retained", "Network trend before churn — ⚠️ synthetic telemetry",
         "![](img/network_trend_churned_vs_retained.png)"),
        ("08_risk_segments", "Model risk segments × contract", ""),
    ]
    for key, title, img in sections:
        df = analytics.get(key)
        if df is None or not len(df):
            continue
        parts.append(f"## {title}\n")
        if img:
            parts.append(img + "\n")
        show = df.head(12) if key == "03_tenure_curve" else df
        parts.append(_md_table(show) + "\n")
        parts.append(f"_Query: `sql/analytics/{key}.sql`_\n")

    if runs:
        parts.append("## Churn model\n")
        parts.append("![](img/roc_curves.png)\n")
        rows = []
        for name, run in runs.items():
            m = run.metrics
            rows.append({"feature set": name, "engine": m["engine"], "AUC (test)": m["roc_auc_test"],
                         "F1 @0.5": m["at_0_50"]["f1"], "recall @0.5": m["at_0_50"]["recall"],
                         "best-F1 threshold": m["best_f1_threshold"], "F1 @best": m["at_best_f1"]["f1"]})
            if "gradient_boosting" in m:
                rows.append({"feature set": name, "engine": m["gradient_boosting"]["engine"],
                             "AUC (test)": m["gradient_boosting"]["roc_auc_test"],
                             "F1 @0.5": m["gradient_boosting"]["at_0_50"]["f1"],
                             "recall @0.5": m["gradient_boosting"]["at_0_50"]["recall"],
                             "best-F1 threshold": "", "F1 @best": ""})
        parts.append(_md_table(pd.DataFrame(rows)) + "\n")
        parts.append("> The **customer** feature set is the honest benchmark (real columns only). "
                     "**customer_network** adds synthetic telemetry that was generated with a churn "
                     "signal built in, so its extra lift is illustrative.\n")
        first = next(iter(runs))
        parts.append(f"### Top drivers ({first} features)\n")
        parts.append(f"![](img/churn_drivers_{first}.png)\n")
        parts.append(_md_table(runs[first].drivers.head(12)) + "\n")
        parts.append(f"### Gain chart ({first} features)\n")
        parts.append(f"![](img/gain_chart_{first}.png)\n")
        parts.append(_md_table(runs[first].lift) + "\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    log.info("findings.md written to %s", out_path)
    return out_path
