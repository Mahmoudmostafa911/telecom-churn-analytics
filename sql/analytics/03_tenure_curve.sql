-- Business question: when do customers leave? Churn rate by tenure month plus
-- the cumulative share of all churn that has happened by that month.
WITH by_month AS (
    SELECT
        d.tenure_months,
        COUNT(*)          AS customers,
        SUM(f.churn_flag) AS churned
    FROM fact_customer AS f
    JOIN dim_customer  AS d ON d.customer_key = f.customer_key
    GROUP BY d.tenure_months
)
SELECT
    tenure_months,
    customers,
    churned,
    ROUND(100.0 * churned / customers, 1)                                        AS churn_rate_pct,
    SUM(churned) OVER (ORDER BY tenure_months ROWS UNBOUNDED PRECEDING)          AS cumulative_churned,
    ROUND(100.0 * SUM(churned) OVER (ORDER BY tenure_months ROWS UNBOUNDED PRECEDING)
          / SUM(churned) OVER (), 1)                                             AS cumulative_churn_share_pct
FROM by_month
ORDER BY tenure_months;
