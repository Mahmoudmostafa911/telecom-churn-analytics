-- Business question: does network experience separate churners from stayers?
-- NOTE: network KPIs are SYNTHETIC in this project (see data/README.md).
SELECT
    f.network_quality_band,
    COUNT(*)                                                     AS customers,
    SUM(f.churn_flag)                                            AS churned,
    ROUND(100.0 * SUM(f.churn_flag) / COUNT(*), 1)               AS churn_rate_pct,
    ROUND(AVG(CAST(f.network_quality_score AS FLOAT)), 1)        AS avg_quality_score,
    ROUND(AVG(CAST(f.avg_dropped_call_pct AS FLOAT)), 2)         AS avg_dropped_call_pct,
    ROUND(AVG(CAST(f.avg_latency_ms AS FLOAT)), 1)               AS avg_latency_ms,
    ROUND(AVG(CAST(f.total_outage_minutes AS FLOAT)), 0)         AS avg_outage_minutes,
    ROUND(AVG(CAST(f.network_complaints AS FLOAT)), 2)           AS avg_complaints
FROM fact_customer AS f
WHERE f.kpi_months > 0
GROUP BY f.network_quality_band
ORDER BY avg_quality_score;
