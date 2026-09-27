-- Business question: does network quality degrade in the months before churn?
-- Monthly KPI averages for churned vs. retained customers across the window.
-- NOTE: the telemetry is SYNTHETIC and was generated with this pattern built in;
-- the query shows HOW to test the hypothesis, not a real-world finding.
SELECT
    d.month,
    d.month_index,
    CASE WHEN f.churn_flag = 1 THEN 'Churned' ELSE 'Retained' END AS customer_group,
    COUNT(*)                                                  AS customer_months,
    ROUND(AVG(CAST(n.dropped_call_pct AS FLOAT)), 3)          AS avg_dropped_call_pct,
    ROUND(AVG(CAST(n.avg_latency_ms AS FLOAT)), 1)            AS avg_latency_ms,
    ROUND(AVG(CAST(n.avg_download_mbps AS FLOAT)), 1)         AS avg_download_mbps,
    ROUND(AVG(CAST(n.outage_minutes AS FLOAT)), 1)            AS avg_outage_minutes,
    ROUND(AVG(CAST(n.complaints AS FLOAT)), 3)                AS avg_complaints
FROM fact_network_monthly AS n
JOIN dim_date       AS d ON d.month_key     = n.month_key
JOIN fact_customer  AS f ON f.customer_key  = n.customer_key
GROUP BY d.month, d.month_index, CASE WHEN f.churn_flag = 1 THEN 'Churned' ELSE 'Retained' END
ORDER BY d.month_index, customer_group;
