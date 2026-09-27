-- Business question: which service/payment combinations concentrate churn?
-- Fiber-optic + electronic check is the classic hot spot in this dataset.
SELECT
    s.internet_service,
    c.payment_method,
    COUNT(*)                                                     AS customers,
    SUM(f.churn_flag)                                            AS churned,
    ROUND(100.0 * SUM(f.churn_flag) / COUNT(*), 1)               AS churn_rate_pct,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)           AS share_of_base_pct,
    RANK() OVER (ORDER BY 1.0 * SUM(f.churn_flag) / COUNT(*) DESC) AS churn_rank
FROM fact_customer AS f
JOIN dim_services  AS s ON s.services_key = f.services_key
JOIN dim_contract  AS c ON c.contract_key = f.contract_key
GROUP BY s.internet_service, c.payment_method
ORDER BY churn_rate_pct DESC;
