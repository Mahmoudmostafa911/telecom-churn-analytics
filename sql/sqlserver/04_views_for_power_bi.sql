/* =============================================================================
   Thin reporting views for Power BI (Import or DirectQuery). Keeping the model
   logic in views means the .pbix stays simple and the same numbers appear in
   SSMS, Excel and Power BI.
   ============================================================================= */
USE TelcoChurn;
GO
CREATE OR ALTER VIEW dbo.vw_customer_360 AS
SELECT
    f.customer_key, f.customer_id,
    d.gender, d.senior_citizen, d.partner, d.dependents, d.tenure_months, d.tenure_bucket,
    c.contract, c.paperless_billing, c.payment_method, c.is_auto_payment,
    s.phone_service, s.multiple_lines, s.internet_service, s.online_security, s.online_backup,
    s.device_protection, s.tech_support, s.streaming_tv, s.streaming_movies,
    s.num_addon_services, s.has_internet, s.has_phone, s.has_streaming,
    f.monthly_charges, f.total_charges, f.lifetime_avg_monthly, f.charge_ratio, f.revenue_band,
    f.churn, f.churn_flag, f.churn_probability, f.risk_band,
    f.kpi_months, f.avg_dropped_call_pct, f.avg_download_mbps, f.avg_latency_ms,
    f.total_outage_minutes, f.network_complaints, f.network_quality_score, f.network_quality_band,
    f.dropped_call_trend_pp, f.latency_trend_pct, f.download_trend_pct
FROM dbo.fact_customer AS f
JOIN dbo.dim_customer  AS d ON d.customer_key = f.customer_key
JOIN dbo.dim_contract  AS c ON c.contract_key = f.contract_key
JOIN dbo.dim_services  AS s ON s.services_key = f.services_key;
GO

CREATE OR ALTER VIEW dbo.vw_network_monthly AS
SELECT
    n.customer_key, n.month_key, dd.month, dd.month_start_date, dd.month_index, dd.months_before_snapshot,
    f.churn_flag, s.internet_service,
    n.dropped_call_pct, n.avg_download_mbps, n.avg_latency_ms, n.outage_minutes, n.data_usage_gb, n.complaints
FROM dbo.fact_network_monthly AS n
JOIN dbo.dim_date      AS dd ON dd.month_key    = n.month_key
JOIN dbo.fact_customer AS f  ON f.customer_key  = n.customer_key
JOIN dbo.dim_services  AS s  ON s.services_key  = f.services_key;
GO

CREATE OR ALTER VIEW dbo.vw_dq_latest AS
SELECT r.*
FROM dbo.dq_results AS r
WHERE r.run_ts = (SELECT MAX(run_ts) FROM dbo.dq_results);
GO

/* Quick smoke test ------------------------------------------------------------ */
SELECT TOP (5) contract, COUNT(*) AS customers,
       CAST(100.0 * SUM(CAST(churn_flag AS INT)) / COUNT(*) AS DECIMAL(5,1)) AS churn_rate_pct
FROM dbo.vw_customer_360
GROUP BY contract
ORDER BY churn_rate_pct DESC;
GO
