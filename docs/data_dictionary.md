# Data dictionary — `customers_features.csv` / `fact_customer` + dims

_Generated from the pipeline output; source column families: **IBM** (real), **derived**, **telemetry** (synthetic)._

| Column | Type | Family | Description |
|---|---|---|---|
| `customer_id` | str | IBM | Business key from the IBM file (`1234-ABCDE`) |
| `gender` | str | IBM | Female / Male |
| `senior_citizen` | str | IBM | Yes / No (conformed from 0/1) |
| `partner` | str | IBM | Has a partner |
| `dependents` | str | IBM | Has dependents |
| `tenure_months` | int64 | IBM | Months with the company (0–72) |
| `phone_service` | str | IBM | Yes / No |
| `multiple_lines` | str | IBM | Yes / No / No phone service |
| `internet_service` | str | IBM | DSL / Fiber optic / No |
| `online_security` | str | IBM | Add-on |
| `online_backup` | str | IBM | Add-on |
| `device_protection` | str | IBM | Add-on |
| `tech_support` | str | IBM | Add-on |
| `streaming_tv` | str | IBM | Add-on |
| `streaming_movies` | str | IBM | Add-on |
| `contract` | str | IBM | Month-to-month / One year / Two year |
| `paperless_billing` | str | IBM | Yes / No |
| `payment_method` | str | IBM | 4 methods; '(automatic)' = auto-pay |
| `monthly_charges` | float64 | IBM | Current monthly bill ($) |
| `total_charges` | float64 | IBM | Lifetime billed ($); blanks for tenure 0 imputed as 0 |
| `churn` | str | IBM | Target label Yes / No |
| `churn_flag` | int64 | derived | 1 = churned |
| `tenure_bucket` | str | derived | 00-12 / 13-24 / 25-48 / 49-72 months |
| `num_addon_services` | int64 | derived | Count of the six add-ons set to Yes (0–6) |
| `has_internet` | int64 | derived | 1 if internet_service != No |
| `has_phone` | int64 | derived | 1 if phone_service = Yes |
| `has_streaming` | int64 | derived | 1 if any streaming add-on |
| `is_auto_payment` | int64 | derived | 1 if payment method is automatic |
| `is_month_to_month` | int64 | derived | 1 if contract = Month-to-month |
| `lifetime_avg_monthly` | float64 | derived | total_charges / tenure_months (monthly_charges when tenure = 0) |
| `charge_ratio` | float64 | derived | monthly_charges / lifetime_avg_monthly (>1 = paying more than historically) |
| `revenue_band` | str | derived | Quartile of monthly_charges: Low / Mid / High / Premium |
| `kpi_months` | int64 | telemetry | Telemetry months available (0 = no telemetry) |
| `avg_dropped_call_pct` | float64 | telemetry | 12-m mean dropped-call % (phone customers) |
| `avg_download_mbps` | float64 | telemetry | 12-m mean download speed (internet customers) |
| `avg_latency_ms` | float64 | telemetry | 12-m mean latency |
| `total_outage_minutes` | int64 | telemetry | 12-m outage minutes |
| `avg_data_usage_gb` | float64 | telemetry | 12-m mean monthly data usage |
| `network_complaints` | int64 | telemetry | 12-m complaints |
| `l3m_dropped_call_pct` | float64 | telemetry | Last-3-month mean dropped-call % |
| `l3m_download_mbps` | float64 | telemetry | Last-3-month mean download |
| `l3m_latency_ms` | float64 | telemetry | Last-3-month mean latency |
| `l3m_outage_minutes` | int64 | telemetry | Last-3-month outage minutes |
| `l3m_complaints` | int64 | telemetry | Last-3-month complaints |
| `dropped_call_trend_pp` | float64 | telemetry | l3m − 12-m dropped-call %, percentage points (+ = worse) |
| `latency_trend_pct` | float64 | telemetry | l3m vs 12-m latency, % (+ = worse) |
| `download_trend_pct` | float64 | telemetry | l3m vs 12-m download, % (− = worse) |
| `network_quality_score` | float64 | telemetry | 0–100 composite, relative to the customer's access technology |
| `network_quality_band` | str | telemetry | Poor / Fair / Good / Excellent / No telemetry |
| `churn_probability` | float64 | derived | Model probability (customer feature set) |
| `risk_band` | str | derived | Low < 0.20 ≤ Medium < 0.50 ≤ High |
| `is_test_row` | int64 | derived | 1 if the row was in the model hold-out set |

## Telemetry fact — `fact_network_monthly` (synthetic)

| Column | Description |
|---|---|
| `customer_key`, `month_key` | Surrogate keys to `dim_customer`, `dim_date` |
| `month`, `month_index` | `YYYY-MM`; 1 = oldest, 12 = snapshot month |
| `dropped_call_pct` | Dropped calls as % of calls (phone customers) |
| `avg_download_mbps`, `avg_latency_ms`, `data_usage_gb` | Internet customers only |
| `outage_minutes` | Minutes of service outage in the month |
| `complaints` | Network complaints logged in the month |