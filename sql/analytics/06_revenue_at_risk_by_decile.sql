-- Business question: is churn a low-value or high-value problem? Split the
-- base into monthly-charge deciles (NTILE) and compare churn + revenue share.
WITH ranked AS (
    SELECT
        f.customer_key,
        f.monthly_charges,
        f.churn_flag,
        NTILE(10) OVER (ORDER BY f.monthly_charges) AS charge_decile
    FROM fact_customer AS f
)
SELECT
    charge_decile,
    COUNT(*)                                               AS customers,
    ROUND(MIN(monthly_charges), 2)                         AS min_monthly,
    ROUND(MAX(monthly_charges), 2)                         AS max_monthly,
    ROUND(100.0 * SUM(churn_flag) / COUNT(*), 1)           AS churn_rate_pct,
    ROUND(SUM(CASE WHEN churn_flag = 1 THEN monthly_charges ELSE 0 END), 2)
                                                           AS monthly_revenue_lost,
    ROUND(100.0 * SUM(CASE WHEN churn_flag = 1 THEN monthly_charges ELSE 0 END)
          / SUM(SUM(CASE WHEN churn_flag = 1 THEN monthly_charges ELSE 0 END)) OVER (), 1)
                                                           AS share_of_lost_revenue_pct
FROM ranked
GROUP BY charge_decile
ORDER BY charge_decile;
