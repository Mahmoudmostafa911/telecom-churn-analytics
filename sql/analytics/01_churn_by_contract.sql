-- Business question: how does contract type drive churn and how much monthly
-- revenue walks out of the door with churned customers?
-- Portable SQL: runs unchanged on SQLite (pipeline) and SQL Server (SSMS).
SELECT
    c.contract,
    COUNT(*)                                                   AS customers,
    SUM(f.churn_flag)                                          AS churned,
    ROUND(100.0 * SUM(f.churn_flag) / COUNT(*), 1)             AS churn_rate_pct,
    ROUND(AVG(CAST(f.monthly_charges AS FLOAT)), 2)            AS avg_monthly_charges,
    ROUND(SUM(CASE WHEN f.churn_flag = 1 THEN f.monthly_charges ELSE 0 END), 2)
                                                               AS monthly_revenue_lost,
    ROUND(100.0 * SUM(CASE WHEN f.churn_flag = 1 THEN f.monthly_charges ELSE 0 END)
          / SUM(f.monthly_charges), 1)                         AS revenue_lost_pct
FROM fact_customer AS f
JOIN dim_contract  AS c ON c.contract_key = f.contract_key
GROUP BY c.contract
ORDER BY churn_rate_pct DESC;
