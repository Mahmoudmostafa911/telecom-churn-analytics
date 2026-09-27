"""Pipeline orchestration + command-line interface.

    python -m telco_churn run                       # real data (after download_data.py)
    python -m telco_churn run --fixture             # synthetic fixture (CI / no internet)
    python -m telco_churn run --no-model            # skip the scoring step
    python -m telco_churn run --raw path.csv --kpis kpis.csv --skip-dq-fail

Every step logs its row counts and duration; a ``run_manifest.json`` is written
to ``data/processed`` for traceability.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

from . import charts, clean, config, features, ingest, model, quality, report, warehouse

log = logging.getLogger("telco_churn")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def run(raw_path: Path, kpi_path: Path | None, with_model: bool = True,
        fail_on_dq: bool = True, expected_rows: int | None = None) -> dict:
    t0 = time.perf_counter()
    manifest: dict = {"raw_file": str(raw_path), "kpi_file": str(kpi_path) if kpi_path else None,
                      "steps": {}}

    def mark(step: str, **info):
        manifest["steps"][step] = {"elapsed_s": round(time.perf_counter() - t0, 2), **info}
        log.info("✔ %s %s", step, info if info else "")

    # 1. ingest + clean
    raw = ingest.load_raw_telco(raw_path)
    customers, cleaning = clean.clean_telco(raw)
    mark("clean", rows=len(customers), blanks_fixed=cleaning.total_charges_blank)

    # 2. telemetry (optional)
    kpis = None
    if kpi_path and Path(kpi_path).exists():
        kpis = ingest.load_network_kpis(kpi_path)
        mark("load_kpis", rows=len(kpis))
    else:
        log.warning("No KPI file — network features and network analytics will be skipped")

    # 3. features
    feats = features.build_features(customers, kpis)
    mark("features", columns=feats.shape[1])

    # 4. quality gate (audit trail is saved even if it raises)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    try:
        dq = quality.run_quality_gate(feats, kpis, expected_rows=expected_rows, fail_on_error=fail_on_dq)
    except quality.DataQualityError:
        dq = quality.run_quality_gate(feats, kpis, expected_rows=expected_rows, fail_on_error=False)
        dq.to_csv(config.PROCESSED_DIR / "dq_results.csv", index=False, lineterminator="\n")
        raise
    dq.to_csv(config.PROCESSED_DIR / "dq_results.csv", index=False, lineterminator="\n")
    mark("quality_gate", **dq["status"].value_counts().to_dict())

    # 5. model
    runs: dict[str, model.ModelRun] = {}
    if with_model:
        runs["customer"] = model.train_churn_model(feats, "customer")
        if kpis is not None:
            runs["customer_network"] = model.train_churn_model(feats, "customer_network")
        feats = model.attach_scores(feats, runs["customer"])  # honest model drives the risk bands
        model.save_model_artifacts(runs)
        feats[["customer_id", "churn_flag", "churn_probability", "risk_band", "is_test_row"]].to_csv(
            config.PROCESSED_DIR / "scores.csv", index=False, lineterminator="\n")
        mark("model", **{k: r.metrics["roc_auc_test"] for k, r in runs.items()})

    feats.to_csv(config.PROCESSED_DIR / "customers_features.csv", index=False)

    # 6. star schema → CSV + SQLite
    tables = warehouse.build_star_schema(feats, kpis)
    warehouse.write_star_csvs(tables)
    warehouse.load_sqlite(tables)
    with sqlite3.connect(config.DB_PATH) as conn:
        dq.to_sql("dq_results", conn, if_exists="replace", index=False)
        if runs:
            pd.DataFrame([{"feature_set": k, "engine": r.engine, "roc_auc_test": r.metrics["roc_auc_test"],
                           "f1_at_050": r.metrics["at_0_50"]["f1"]} for k, r in runs.items()]
                         ).to_sql("model_metrics", conn, if_exists="replace", index=False)
    mark("warehouse", **{k: len(v) for k, v in tables.items()})

    # 7. analytics SQL
    analytics = warehouse.run_analytics_sql()
    mark("analytics_sql", queries=len(analytics))

    # 8. charts + findings
    charts.render_all(analytics, runs)
    is_fixture = "fixture" in raw_path.name.lower()
    report.build_findings(analytics, runs, cleaning.as_dict(), dq, raw_path, len(customers), is_fixture)
    mark("report")

    manifest["total_elapsed_s"] = round(time.perf_counter() - t0, 2)
    manifest["cleaning_report"] = cleaning.as_dict()
    (config.PROCESSED_DIR / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("Pipeline finished in %.1fs", manifest["total_elapsed_s"])
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="telco_churn", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="run the full pipeline")
    p.add_argument("--raw", type=Path, default=None, help="raw Telco CSV (default: data/raw/Telco-Customer-Churn.csv)")
    p.add_argument("--kpis", type=Path, default=config.DEFAULT_KPI_FILE, help="network KPI CSV")
    p.add_argument("--fixture", action="store_true", help="use the synthetic fixture instead of the real file")
    p.add_argument("--no-model", action="store_true", help="skip model training")
    p.add_argument("--skip-dq-fail", action="store_true", help="continue even if a FAIL check trips")
    p.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    if args.fixture:
        raw = config.FIXTURE_RAW_FILE
        expected = None
    else:
        raw = args.raw or config.DEFAULT_RAW_FILE
        expected = config.EXPECTED_REAL_ROWS if raw == config.DEFAULT_RAW_FILE else None
    try:
        run(raw, args.kpis, with_model=not args.no_model, fail_on_dq=not args.skip_dq_fail,
            expected_rows=expected)
    except (FileNotFoundError, ingest.SchemaError, quality.DataQualityError) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
