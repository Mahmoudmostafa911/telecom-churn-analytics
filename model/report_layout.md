# Power BI report layout

Five pages, 16:9, light theme with teal `#117865` (primary), navy `#1F2A44` (text),
red `#C0392B` reserved for "churned / at risk". Every page carries the same
slicer panel on the left: **Contract · Internet service · Payment method · Tenure bucket · Risk band**.

## Page 1 — Executive summary
| Visual | Fields | Notes |
|---|---|---|
| KPI cards (5) | `Customers`, `Churn Rate`, `MRR Lost to Churn`, `Expected MRR at Risk`, `DQ Status Label` | DQ card links to page 5 |
| Clustered bar | `Churn Rate` by `dim_contract[contract]` | Sort descending, data labels on |
| Matrix (heat-map) | rows `payment_method`, cols `internet_service`, values `Churn Rate` | Conditional formatting: background colour scale white → red |
| Line + column | X `dim_customer[tenure_months]`, columns `Customers`, line `Churn Rate` | Reproduces `docs/img/tenure_curve.png` |
| Text box | 3-bullet "So what" | Pull the wording from `docs/findings.md` |

## Page 2 — Churn drivers
| Visual | Fields | Notes |
|---|---|---|
| **Key influencers** | Analyze `fact_customer[churn]` = "Yes"; explain by contract, internet_service, payment_method, tech_support, online_security, senior_citizen, paperless_billing, tenure_bucket, num_addon_services | Native AI visual — no code |
| **Decomposition tree** | Analyze `Churn Rate`; explain by contract → internet_service → payment_method → tenure_bucket | Turn on "High value" AI split |
| Bar | `Churn Lift vs Base` by `dim_services[tech_support]` (filter `has_internet` = 1) | Shows the retention value of tech support |
| Table | `drivers_customer.csv` imported as a small table: feature, odds_ratio, direction | Import from `model/` folder |

## Page 3 — Network quality (⚠ synthetic telemetry)
| Visual | Fields | Notes |
|---|---|---|
| Banner text | "Telemetry is synthetic — demonstrates the join and the analysis pattern" | Keep it visible; honesty is part of the portfolio |
| Column | `Churn Rate` by `fact_customer[network_quality_band]` | Sort Poor → Excellent |
| Line (2 series) | X `dim_date[month_index]`, Y `Avg Latency – Churned`, `Avg Latency – Retained` | Same for `Avg Dropped Call %` |
| Scatter | X `Avg Network Quality Score`, Y `Churn Rate`, legend `internet_service`, size `Customers`, detail `tenure_bucket` | Shows the technology confounder |
| Cards | `Outage Minutes`, `Complaints per 1k Customer-Months`, `Latency Trend %` | Filtered to `months_before_snapshot < 3` |

## Page 4 — Retention targeting
| Visual | Fields | Notes |
|---|---|---|
| Matrix | rows `risk_band`, cols `contract`, values `Customers`, `Churn Rate`, `Expected MRR at Risk` | Mirrors `sql/analytics/08_risk_segments.sql` |
| Gain chart | Import `model/lift_customer.csv`; line of `cumulative_churners_pct` over `cumulative_customers_pct` | Annotate "top 20 % of customers hold ≈ X % of churners" |
| Table (drill-through target) | `customer_id`, `contract`, `tenure_months`, `monthly_charges`, `churn_probability`, `risk_band`, `network_quality_band` | Sort by probability desc; export list for the retention team |
| Slicer | `risk_band` default = High | |

## Page 5 — Data quality & lineage
| Visual | Fields | Notes |
|---|---|---|
| Cards | `DQ Pass Rate`, `DQ Checks Total`, `dq_results[run_ts]` (last refresh) | |
| Table | `dq_results`: check_name, table, status, observed, expectation | Conditional icons: PASS ✅ WARN ⚠ FAIL ❌ |
| Text | Source lineage: IBM Telco (real) → clean → features → quality gate → star → model | Paste the Mermaid diagram as an image (`docs/img/architecture.png`) |

## Build order (≈ 2 hours)
1. Import the six CSVs from `data/processed/star/` plus `dq_results.csv`, `drivers_customer.csv`, `lift_customer.csv`.
2. Create relationships per `star_schema.md`; mark `dim_date` as date table.
3. Paste the measures from `dax_measures.md` into a `_Measures` table.
4. Build pages 1 → 5; apply the theme JSON (`model/theme.json`).
5. Screenshot each page to `docs/img/pbi_page_N.png` and reference them in README.
