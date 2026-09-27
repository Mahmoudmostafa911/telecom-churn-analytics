"""Static charts for README / findings.md (matplotlib, headless)."""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from . import config  # noqa: E402

log = logging.getLogger(__name__)

TEAL, NAVY, GREY, RED, LIGHT = "#117865", "#1F2A44", "#8A94A6", "#C0392B", "#DDE3EA"
plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 160, "font.family": "DejaVu Sans", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold",
    "axes.titlesize": 12, "axes.grid": True, "grid.alpha": 0.25,
})


def _save(fig, name: str, img_dir: Path) -> Path:
    img_dir.mkdir(parents=True, exist_ok=True)
    p = img_dir / name
    fig.tight_layout()
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p


def _bar(ax, labels, values, color=TEAL, fmt="{:.1f}%"):
    bars = ax.bar(labels, values, color=color, width=0.6)
    for b, v in zip(bars, values):
        ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=9, xytext=(0, 2), textcoords="offset points")
    ax.set_ylim(0, max(values) * 1.18 if len(values) else 1)


def churn_by_contract(df: pd.DataFrame, img_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    d = df.sort_values("churn_rate_pct", ascending=False)
    _bar(ax, d["contract"], d["churn_rate_pct"], color=[RED, TEAL, NAVY][: len(d)])
    ax.set_title("Churn rate by contract type")
    ax.set_ylabel("Churn rate (%)")
    return _save(fig, "churn_by_contract.png", img_dir)


def churn_by_segment_grid(internet_payment: pd.DataFrame, img_dir: Path) -> Path:
    piv = internet_payment.pivot(index="payment_method", columns="internet_service", values="churn_rate_pct")
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    im = ax.imshow(piv.to_numpy(), cmap="Reds", aspect="auto")
    ax.set_xticks(range(piv.shape[1]), piv.columns)
    ax.set_yticks(range(piv.shape[0]), piv.index)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.iloc[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v:.0f}%", ha="center", va="center",
                        color="white" if v > 30 else NAVY, fontsize=10, fontweight="bold")
    ax.grid(False)
    ax.set_title("Churn rate: internet service × payment method")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="Churn %")
    return _save(fig, "churn_heatmap_internet_payment.png", img_dir)


def tenure_curve(df: pd.DataFrame, img_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    d = df[df["tenure_months"] > 0]
    ax.plot(d["tenure_months"], d["churn_rate_pct"], color=TEAL, lw=2, label="Churn rate by tenure month")
    ax2 = ax.twinx()
    ax2.plot(d["tenure_months"], d["cumulative_churn_share_pct"], color=NAVY, lw=1.5, ls="--",
             label="Cumulative share of all churn")
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("Cumulative % of churners")
    ax2.grid(False)
    ax.set_xlabel("Tenure (months)")
    ax.set_ylabel("Churn rate (%)")
    ax.set_title("When customers leave: churn by tenure")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, frameon=False)
    return _save(fig, "tenure_curve.png", img_dir)


def network_quality_vs_churn(df: pd.DataFrame, img_dir: Path) -> Path:
    order = ["Poor", "Fair", "Good", "Excellent"]
    d = df.set_index("network_quality_band").reindex([o for o in order if o in set(df["network_quality_band"])]).reset_index()
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    _bar(ax, d["network_quality_band"], d["churn_rate_pct"], color=TEAL)
    ax.set_title("Churn rate by network quality band  (telemetry is synthetic)")
    ax.set_ylabel("Churn rate (%)")
    return _save(fig, "network_quality_vs_churn.png", img_dir)


def network_trend(df: pd.DataFrame, img_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6))
    for grp, color in [("Churned", RED), ("Retained", TEAL)]:
        d = df[df["customer_group"] == grp]
        axes[0].plot(d["month_index"], d["avg_dropped_call_pct"], marker="o", color=color, label=grp)
        axes[1].plot(d["month_index"], d["avg_latency_ms"], marker="o", color=color, label=grp)
    axes[0].set_title("Dropped-call % by month before snapshot")
    axes[1].set_title("Latency (ms) by month before snapshot")
    for ax in axes:
        ax.set_xlabel("Month in observation window (12 = latest)")
        ax.legend(frameon=False)
    fig.suptitle("Synthetic telemetry: degradation pattern for churners", fontsize=11, fontweight="bold")
    return _save(fig, "network_trend_churned_vs_retained.png", img_dir)


def roc_curves(runs: dict, img_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    for (name, run), color in zip(runs.items(), [TEAL, NAVY, RED]):
        ax.plot(run.roc["fpr"], run.roc["tpr"], color=color, lw=2,
                label=f"{name}  (AUC {run.metrics['roc_auc_test']:.3f})")
    ax.plot([0, 1], [0, 1], color=GREY, ls="--", lw=1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC — hold-out set")
    ax.legend(loc="lower right", frameon=False)
    return _save(fig, "roc_curves.png", img_dir)


def driver_chart(drivers: pd.DataFrame, img_dir: Path, name: str = "customer", top: int = 12) -> Path:
    d = drivers.head(top).iloc[::-1]
    colors = [RED if c > 0 else TEAL for c in d["coefficient"]]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.barh(d["feature"], d["coefficient"], color=colors)
    ax.axvline(0, color=NAVY, lw=1)
    ax.set_title(f"Top churn drivers — logistic regression coefficients ({name} features)")
    ax.set_xlabel("Coefficient (log-odds; red = increases churn, teal = reduces churn)")
    return _save(fig, f"churn_drivers_{name}.png", img_dir)


def lift_chart(lift: pd.DataFrame, img_dir: Path, name: str = "customer") -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.plot(lift["cumulative_customers_pct"], lift["cumulative_churners_pct"], marker="o", color=TEAL, lw=2,
            label="Model")
    ax.plot([0, 100], [0, 100], color=GREY, ls="--", label="Random")
    for _, r in lift.iterrows():
        if r["decile"] in (2, 3, 5):
            ax.annotate(f"{r['cumulative_churners_pct']:.0f}% of churners in top {r['cumulative_customers_pct']:.0f}%",
                        (r["cumulative_customers_pct"], r["cumulative_churners_pct"]),
                        xytext=(8, -12), textcoords="offset points", fontsize=8, color=NAVY)
    ax.set_xlabel("% of customers targeted (ranked by predicted risk)")
    ax.set_ylabel("% of actual churners captured")
    ax.set_title("Gain chart — who to call first")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, f"gain_chart_{name}.png", img_dir)


def render_all(analytics: dict[str, pd.DataFrame], runs: dict, img_dir: Path = config.IMG_DIR) -> list[Path]:
    out = []
    if "01_churn_by_contract" in analytics:
        out.append(churn_by_contract(analytics["01_churn_by_contract"], img_dir))
    if "02_churn_by_internet_and_payment" in analytics:
        out.append(churn_by_segment_grid(analytics["02_churn_by_internet_and_payment"], img_dir))
    if "03_tenure_curve" in analytics:
        out.append(tenure_curve(analytics["03_tenure_curve"], img_dir))
    if "05_network_quality_vs_churn" in analytics and len(analytics["05_network_quality_vs_churn"]):
        out.append(network_quality_vs_churn(analytics["05_network_quality_vs_churn"], img_dir))
    if "07_network_trend_churned_vs_retained" in analytics and len(analytics["07_network_trend_churned_vs_retained"]):
        out.append(network_trend(analytics["07_network_trend_churned_vs_retained"], img_dir))
    if runs:
        out.append(roc_curves(runs, img_dir))
        for name, run in runs.items():
            out.append(driver_chart(run.drivers, img_dir, name))
        first = next(iter(runs))
        out.append(lift_chart(runs[first].lift, img_dir, first))
    log.info("Rendered %s charts to %s", len(out), img_dir)
    return out
