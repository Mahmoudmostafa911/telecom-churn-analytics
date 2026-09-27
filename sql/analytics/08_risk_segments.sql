-- Business question: where should retention budget go? Model risk band x
-- contract, with the revenue that sits in each cell. Requires the scoring step.
SELECT
    COALESCE(f.risk_band, 'Unscored')                       AS risk_band,
    c.contract,
    COUNT(*)                                                AS customers,
    ROUND(100.0 * SUM(f.churn_flag) / COUNT(*), 1)          AS actual_churn_rate_pct,
    ROUND(AVG(CAST(f.churn_probability AS FLOAT)), 3)       AS avg_predicted_probability,
    ROUND(SUM(f.monthly_charges), 2)                        AS monthly_revenue,
    ROUND(SUM(f.monthly_charges * COALESCE(f.churn_probability, 0)), 2)
                                                            AS expected_monthly_revenue_at_risk
FROM fact_customer AS f
JOIN dim_contract  AS c ON c.contract_key = f.contract_key
GROUP BY COALESCE(f.risk_band, 'Unscored'), c.contract
ORDER BY avg_predicted_probability DESC, monthly_revenue DESC;
