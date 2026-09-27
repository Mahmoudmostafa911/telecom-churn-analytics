-- Business question: do protective add-ons (tech support, online security)
-- retain internet customers? Compare churn by add-on count and by tech support.
SELECT
    'By add-on count'              AS analysis,
    CAST(s.num_addon_services AS VARCHAR(20)) AS segment,
    COUNT(*)                                             AS customers,
    ROUND(100.0 * SUM(f.churn_flag) / COUNT(*), 1)       AS churn_rate_pct,
    ROUND(AVG(CAST(f.monthly_charges AS FLOAT)), 2)      AS avg_monthly_charges
FROM fact_customer AS f
JOIN dim_services  AS s ON s.services_key = f.services_key
WHERE s.has_internet = 1
GROUP BY s.num_addon_services

UNION ALL

SELECT
    'By tech support'              AS analysis,
    s.tech_support                 AS segment,
    COUNT(*)                                             AS customers,
    ROUND(100.0 * SUM(f.churn_flag) / COUNT(*), 1)       AS churn_rate_pct,
    ROUND(AVG(CAST(f.monthly_charges AS FLOAT)), 2)      AS avg_monthly_charges
FROM fact_customer AS f
JOIN dim_services  AS s ON s.services_key = f.services_key
WHERE s.has_internet = 1
GROUP BY s.tech_support
ORDER BY analysis, segment;
