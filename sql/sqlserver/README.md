# SQL Server scripts

| Order | Script | Purpose |
|---|---|---|
| 1 | `01_create_database_and_tables.sql` | Creates `TelcoChurn` and the star schema (PK/FK/indexes) |
| 2 | `02_bulk_load_from_csv.sql` | `BULK INSERT` of `data/processed/star/*.csv` + `dq_results.csv` (edit `@Root`) |
| 3 | `03_merge_refresh_scores.sql` | `MERGE` pattern to refresh model scores incrementally |
| 4 | `04_views_for_power_bi.sql` | `vw_customer_360`, `vw_network_monthly`, `vw_dq_latest` for Power BI |
| 5 | `../analytics/*.sql` | The eight business queries — written in portable SQL, run them as-is in SSMS |

The pipeline itself uses SQLite so it runs anywhere; these scripts recreate the
identical structure on SQL Server so the same analytics queries and a Power BI
model can sit on top of a proper database engine.
