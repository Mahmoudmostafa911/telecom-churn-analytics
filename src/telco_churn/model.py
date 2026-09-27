"""Churn propensity model with interpretable drivers.

Two feature sets are trained and reported side by side:

* ``customer``          – IBM columns only (**real data, honest benchmark**)
* ``customer_network``  – adds the synthetic network telemetry aggregates.
  Because the telemetry was *generated* with a churn signal built in, its lift
  is illustrative only. It shows how operational data would be wired into the
  model, not a real-world result. README says this loudly.

scikit-learn is used when available (``LogisticRegression`` + ``HistGradientBoosting``).
If it is not installed — e.g. in a locked-down CI runner — a compact NumPy
implementation of L2-regularised logistic regression (Newton–Raphson) keeps
the pipeline fully runnable with pandas + numpy only.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)

try:  # optional dependency
    from sklearn.linear_model import LogisticRegression as _SkLogit
    from sklearn.ensemble import HistGradientBoostingClassifier as _SkGBM
    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment
    SKLEARN_AVAILABLE = False

CATEGORICAL_FEATURES = [
    "gender", "senior_citizen", "partner", "dependents", "phone_service", "multiple_lines",
    "internet_service", "online_security", "online_backup", "device_protection",
    "tech_support", "streaming_tv", "streaming_movies", "contract", "paperless_billing",
    "payment_method",
]
NUMERIC_CUSTOMER_FEATURES = ["tenure_months", "monthly_charges", "total_charges",
                             "num_addon_services", "charge_ratio"]
NUMERIC_NETWORK_FEATURES = ["avg_dropped_call_pct", "avg_latency_ms", "avg_download_mbps",
                            "total_outage_minutes", "network_complaints", "network_quality_score",
                            "dropped_call_trend_pp", "latency_trend_pct", "l3m_complaints"]

FEATURE_SETS = {
    "customer": NUMERIC_CUSTOMER_FEATURES,
    "customer_network": NUMERIC_CUSTOMER_FEATURES + NUMERIC_NETWORK_FEATURES,
}


# --------------------------------------------------------------------------- #
# Minimal NumPy logistic regression (fallback)
# --------------------------------------------------------------------------- #
class NumpyLogisticRegression:
    """L2-regularised logistic regression fitted by Newton–Raphson."""

    def __init__(self, l2: float = 1.0, max_iter: int = 100, tol: float = 1e-8):
        self.l2, self.max_iter, self.tol = l2, max_iter, tol
        self.coef_: np.ndarray | None = None
        self.intercept_: float = 0.0
        self.n_iter_: int = 0

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))

    def fit(self, X: np.ndarray, y: np.ndarray) -> "NumpyLogisticRegression":
        Xb = np.hstack([np.ones((X.shape[0], 1)), X])
        w = np.zeros(Xb.shape[1])
        penalty = np.full(Xb.shape[1], self.l2)
        penalty[0] = 0.0  # never shrink the intercept
        for i in range(self.max_iter):
            p = self._sigmoid(Xb @ w)
            grad = Xb.T @ (p - y) + penalty * w
            hess = (Xb * (p * (1 - p))[:, None]).T @ Xb + np.diag(penalty)
            step = np.linalg.solve(hess, grad)
            w -= step
            self.n_iter_ = i + 1
            if np.max(np.abs(step)) < self.tol:
                break
        self.intercept_, self.coef_ = float(w[0]), w[1:]
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self._sigmoid(self.intercept_ + X @ self.coef_)


# --------------------------------------------------------------------------- #
# Data preparation
# --------------------------------------------------------------------------- #
@dataclass
class DesignMatrix:
    X: pd.DataFrame
    y: np.ndarray
    numeric_cols: list[str]
    means: pd.Series = field(default_factory=pd.Series)
    stds: pd.Series = field(default_factory=pd.Series)


def build_design_matrix(df: pd.DataFrame, feature_set: str = "customer") -> DesignMatrix:
    numeric = [c for c in FEATURE_SETS[feature_set] if c in df.columns]
    cats = [c for c in CATEGORICAL_FEATURES if c in df.columns]
    X_num = df[numeric].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    X_cat = pd.get_dummies(df[cats].astype(str), drop_first=True, dtype=float)
    X = pd.concat([X_num.astype(float), X_cat], axis=1)
    X.columns = [str(c).replace(" ", "_").replace("(", "").replace(")", "") for c in X.columns]
    y = df["churn_flag"].to_numpy(dtype=float)
    return DesignMatrix(X=X, y=y, numeric_cols=[c for c in X.columns if c in numeric])


def stratified_split(y: np.ndarray, test_size: float = 0.25, seed: int = config.SEED):
    rng = np.random.default_rng(seed)
    test_idx = []
    for cls in np.unique(y):
        idx = np.flatnonzero(y == cls)
        rng.shuffle(idx)
        n_test = int(round(len(idx) * test_size))
        test_idx.append(idx[:n_test])
    test_idx = np.sort(np.concatenate(test_idx))
    mask = np.zeros(len(y), dtype=bool)
    mask[test_idx] = True
    return ~mask, mask


def standardise(dm: DesignMatrix, train_mask: np.ndarray) -> pd.DataFrame:
    X = dm.X.copy()
    dm.means = X.loc[train_mask, dm.numeric_cols].mean()
    dm.stds = X.loc[train_mask, dm.numeric_cols].std(ddof=0).replace(0, 1.0)
    X[dm.numeric_cols] = (X[dm.numeric_cols] - dm.means) / dm.stds
    return X


# --------------------------------------------------------------------------- #
# Metrics (implemented locally so the module has no hard sklearn dependency)
# --------------------------------------------------------------------------- #
def roc_auc(y: np.ndarray, p: np.ndarray) -> float:
    """AUC via the Mann–Whitney U statistic (ties get average ranks)."""
    ranks = pd.Series(p).rank(method="average").to_numpy()
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def classification_metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict:
    pred = (p >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    eps = 1e-12
    logloss = float(-np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
    return {
        "threshold": threshold,
        "accuracy": round((tp + tn) / len(y), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "log_loss": round(logloss, 4),
        "brier": round(float(np.mean((p - y) ** 2)), 4),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def best_f1_threshold(y: np.ndarray, p: np.ndarray) -> float:
    grid = np.round(np.arange(0.10, 0.91, 0.02), 2)
    scores = [(classification_metrics(y, p, t)["f1"], t) for t in grid]
    return float(max(scores)[1])


def decile_lift_table(y: np.ndarray, p: np.ndarray) -> pd.DataFrame:
    df = pd.DataFrame({"y": y, "p": p}).sort_values("p", ascending=False).reset_index(drop=True)
    df["decile"] = (np.arange(len(df)) * 10 // len(df)) + 1
    base_rate = df["y"].mean()
    g = df.groupby("decile").agg(customers=("y", "size"), churners=("y", "sum"),
                                 min_probability=("p", "min"), max_probability=("p", "max"))
    g["min_probability"] = g["min_probability"].round(4)
    g["max_probability"] = g["max_probability"].round(4)
    g["churn_rate"] = (g["churners"] / g["customers"]).round(4)
    g["lift"] = (g["churn_rate"] / base_rate).round(2)
    g["cumulative_churners_pct"] = (g["churners"].cumsum() / g["churners"].sum() * 100).round(1)
    g["cumulative_customers_pct"] = (g["customers"].cumsum() / g["customers"].sum() * 100).round(1)
    return g.reset_index()


def roc_curve_points(y: np.ndarray, p: np.ndarray) -> pd.DataFrame:
    order = np.argsort(-p)
    y_sorted = y[order]
    tps = np.cumsum(y_sorted)
    fps = np.cumsum(1 - y_sorted)
    tpr = tps / max(y.sum(), 1)
    fpr = fps / max((1 - y).sum(), 1)
    return pd.DataFrame({"fpr": np.concatenate([[0], fpr]), "tpr": np.concatenate([[0], tpr])})


def risk_band(prob: float) -> str:
    for lo, hi, label in config.RISK_BANDS:
        if lo <= prob < hi:
            return label
    return config.RISK_BANDS[-1][2]


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
@dataclass
class ModelRun:
    feature_set: str
    engine: str
    metrics: dict
    drivers: pd.DataFrame
    lift: pd.DataFrame
    roc: pd.DataFrame
    probabilities: np.ndarray          # for ALL rows (train + test)
    test_mask: np.ndarray


def _fit_logit(X: np.ndarray, y: np.ndarray):
    if SKLEARN_AVAILABLE:
        m = _SkLogit(C=1.0, max_iter=5000)
        m.fit(X, y)
        return m, "sklearn.LogisticRegression"
    m = NumpyLogisticRegression(l2=1.0).fit(X, y)
    return m, "numpy.NewtonRaphsonLogit"


def _proba(model, X: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba") and SKLEARN_AVAILABLE and not isinstance(model, NumpyLogisticRegression):
        return model.predict_proba(X)[:, 1]
    return model.predict_proba(X)


def train_churn_model(df: pd.DataFrame, feature_set: str = "customer",
                      test_size: float = 0.25, seed: int = config.SEED) -> ModelRun:
    dm = build_design_matrix(df, feature_set)
    train_mask, test_mask = stratified_split(dm.y, test_size, seed)
    X = standardise(dm, train_mask).to_numpy(dtype=float)
    y = dm.y

    logit, engine = _fit_logit(X[train_mask], y[train_mask])
    p_all = _proba(logit, X)
    p_test, y_test = p_all[test_mask], y[test_mask]

    metrics = {
        "feature_set": feature_set,
        "engine": engine,
        "n_train": int(train_mask.sum()),
        "n_test": int(test_mask.sum()),
        "n_features": int(X.shape[1]),
        "base_churn_rate_test": round(float(y_test.mean()), 4),
        "roc_auc_test": round(roc_auc(y_test, p_test), 4),
        "at_0_50": classification_metrics(y_test, p_test, 0.5),
    }
    t_best = best_f1_threshold(y_test, p_test)
    metrics["best_f1_threshold"] = t_best
    metrics["at_best_f1"] = classification_metrics(y_test, p_test, t_best)

    if SKLEARN_AVAILABLE:
        gbm = _SkGBM(max_iter=300, learning_rate=0.05, max_depth=4, random_state=seed)
        gbm.fit(X[train_mask], y[train_mask])
        p_gbm = gbm.predict_proba(X[test_mask])[:, 1]
        metrics["gradient_boosting"] = {
            "engine": "sklearn.HistGradientBoostingClassifier",
            "roc_auc_test": round(roc_auc(y_test, p_gbm), 4),
            "at_0_50": classification_metrics(y_test, p_gbm, 0.5),
        }

    coef = np.asarray(getattr(logit, "coef_")).ravel()
    drivers = pd.DataFrame({
        "feature": dm.X.columns,
        "coefficient": np.round(coef, 4),
        "odds_ratio": np.round(np.exp(coef), 3),
        "abs_coefficient": np.abs(coef),
        "type": ["numeric (per 1 SD)" if c in dm.numeric_cols else "one-hot vs baseline"
                 for c in dm.X.columns],
    }).sort_values("abs_coefficient", ascending=False).drop(columns="abs_coefficient").reset_index(drop=True)
    drivers["direction"] = np.where(drivers["coefficient"] > 0, "increases churn", "reduces churn")

    run = ModelRun(feature_set=feature_set, engine=engine, metrics=metrics, drivers=drivers,
                   lift=decile_lift_table(y_test, p_test), roc=roc_curve_points(y_test, p_test),
                   probabilities=p_all, test_mask=test_mask)
    log.info("Model [%s] via %s: AUC=%.3f  F1@0.5=%.3f", feature_set, engine,
             metrics["roc_auc_test"], metrics["at_0_50"]["f1"])
    return run


def attach_scores(df: pd.DataFrame, run: ModelRun) -> pd.DataFrame:
    """Add churn_probability, risk_band and is_test_row to the feature frame."""
    out = df.copy()
    out["churn_probability"] = np.round(run.probabilities, 4)
    out["risk_band"] = out["churn_probability"].apply(risk_band)
    out["is_test_row"] = run.test_mask.astype(int)
    return out


def save_model_artifacts(runs: dict[str, ModelRun], model_dir: Path = config.MODEL_DIR) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    metrics = {name: r.metrics for name, r in runs.items()}
    metrics["_note"] = ("'customer' uses real IBM columns only. 'customer_network' adds SYNTHETIC "
                        "telemetry generated with a churn signal built in — illustrative, not evidence.")
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    for name, r in runs.items():
        r.drivers.to_csv(model_dir / f"drivers_{name}.csv", index=False)
        r.lift.to_csv(model_dir / f"lift_{name}.csv", index=False)
    log.info("Model artifacts written to %s", model_dir)
