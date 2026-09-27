# Architecture

![architecture](img/architecture.png)

```mermaid
flowchart LR
    subgraph SRC[Sources]
        A1[IBM Telco Customer Churn<br/>7,043 customers · real]
        A2[Network KPIs monthly<br/>~70k rows · synthetic]
    end
    subgraph PY[Python · pandas]
        B1[ingest.py<br/>schema contract] --> B2[clean.py<br/>types · blanks · snake_case]
        B2 --> B3[features.py<br/>tenure buckets · add-ons · ARPU<br/>telemetry aggregates · quality score]
        B3 --> B4{quality.py<br/>rule checks<br/>PASS / WARN / FAIL}
    end
    subgraph STORE[Model & store]
        C1[warehouse.py<br/>star schema → CSV + SQLite]
        C2[(SQL Server<br/>T-SQL DDL · BULK INSERT · MERGE)]
        C3[model.py<br/>logistic regression · GBM<br/>probability · risk band]
    end
    subgraph SERVE[Serve]
        D1[sql/analytics/*.sql<br/>8 portable queries]
        D2[docs/findings.md + charts]
        D3[Power BI<br/>5-page report]
    end
    A1 --> B1
    A2 --> B1
    B4 -- FAIL --> X[stop + dq_results.csv]
    B4 -- PASS/WARN --> C3 --> C1
    C1 --> C2
    C1 --> D1 --> D2
    C1 --> D3
    C2 --> D3
```

## Components

| Layer | Module / asset | Responsibility |
|---|---|---|
| Config | `src/telco_churn/config.py` | paths, schema contract (21 columns), category domains, numeric ranges, business bands |
| Ingest | `ingest.py` | read raw as text, enforce column contract (`SchemaError` on drift) |
| Clean | `clean.py` | `TotalCharges` blanks → 0.0 for tenure 0, 0/1 → Yes/No, snake_case, de-dup, `CleaningReport` |
| Features | `features.py` | tenure buckets, add-on count, auto-pay flag, lifetime ARPU & charge ratio, 12-m / last-3-m telemetry aggregates, trend deltas, technology-relative `network_quality_score` |
| Quality | `quality.py` | ~45 declarative checks → `dq_results` (audit table); FAIL raises `DataQualityError` |
| Model | `model.py` | stratified split, standardisation, logistic regression (sklearn or NumPy fallback), optional gradient boosting, AUC / F1 / lift, odds-ratio driver table, risk bands |
| Warehouse | `warehouse.py` | star schema (4 dims, 2 facts), CSV extracts, SQLite load, execution of portable analytics SQL |
| SQL Server | `sql/sqlserver/*.sql` | DDL with PK/FK/indexes, `BULK INSERT` loader, `MERGE` score refresh, Power BI views |
| Analytics | `sql/analytics/*.sql` | 8 business questions written once, run on SQLite **and** SQL Server |
| Serve | `charts.py`, `report.py`, `model/*.md` | PNG charts, `findings.md`, DAX measures, report layout, theme |
| Orchestration | `pipeline.py` | CLI, step timing, `run_manifest.json` |
| Trust | `tests/`, `.github/workflows/ci.yml` | 23 unit tests + smoke run of the full pipeline on the synthetic fixture on every push |

## Design principles

1. **Contract first.** The raw header is a hard contract; new columns are warned about, missing ones stop the run.
2. **Fail loudly, log everything.** The quality gate writes its audit table *before* raising, so a failed run still leaves evidence.
3. **Write SQL once.** Analytics queries use only the SQL subset shared by SQLite and SQL Server (CTEs, window functions, CASE, CAST — no TOP/LIMIT, no dialect-specific string ops).
4. **Honest about data.** Real vs synthetic is labelled in file names, banners, chart titles and the model report.
5. **Dependency-light.** pandas + numpy + matplotlib are enough to run everything; scikit-learn is optional.
6. **Portable to Fabric.** The star schema is Direct-Lake-ready; the notebooks translate to Fabric notebooks with a path change (`docs` → see `model/star_schema.md`).
