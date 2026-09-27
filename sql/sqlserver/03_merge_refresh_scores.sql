/* =============================================================================
   Incremental refresh pattern: MERGE the latest model scores into fact_customer
   without reloading the whole table. The pipeline writes data/processed/scores.csv
   (customer_id, churn_flag, churn_probability, risk_band, is_test_row) on every run.
   ============================================================================= */
USE TelcoChurn;
GO
IF OBJECT_ID('dbo.stg_scores') IS NOT NULL DROP TABLE dbo.stg_scores;
CREATE TABLE dbo.stg_scores (
    customer_id        VARCHAR(20)   NOT NULL PRIMARY KEY,
    churn_flag         BIT           NOT NULL,
    churn_probability  DECIMAL(6,4)  NOT NULL,
    risk_band          VARCHAR(10)   NOT NULL,
    is_test_row        BIT           NOT NULL
);

BULK INSERT dbo.stg_scores
FROM 'C:\repos\telecom-churn-analytics\data\processed\scores.csv'
WITH (FORMAT = 'CSV', FIRSTROW = 2, ROWTERMINATOR = '0x0a', CODEPAGE = '65001', TABLOCK);

DECLARE @changes TABLE (action_taken NVARCHAR(10));

MERGE dbo.fact_customer AS tgt
USING dbo.stg_scores    AS src
   ON tgt.customer_id = src.customer_id
WHEN MATCHED AND (tgt.churn_probability IS NULL
                  OR tgt.churn_probability <> src.churn_probability
                  OR tgt.risk_band         <> src.risk_band)
    THEN UPDATE SET tgt.churn_probability = src.churn_probability,
                    tgt.risk_band         = src.risk_band
OUTPUT $action INTO @changes;

SELECT action_taken, COUNT(*) AS rows_affected FROM @changes GROUP BY action_taken;

/* Sanity: risk bands must be monotonic in actual churn */
SELECT risk_band,
       COUNT(*)                                            AS customers,
       CAST(100.0 * SUM(CAST(churn_flag AS INT)) / COUNT(*) AS DECIMAL(5,1)) AS actual_churn_rate_pct,
       CAST(AVG(churn_probability) AS DECIMAL(6,3))       AS avg_predicted
FROM dbo.fact_customer
GROUP BY risk_band
ORDER BY avg_predicted DESC;
GO
