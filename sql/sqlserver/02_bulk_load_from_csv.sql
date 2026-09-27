/* =============================================================================
   Load the star-schema CSVs written by the pipeline (data/processed/star/*.csv).
   1. Replace @Root with the absolute folder on the SQL Server machine.
   2. Run 01_create_database_and_tables.sql first.
   BULK INSERT ... FORMAT = 'CSV' requires SQL Server 2017+.
   Load order respects the foreign keys: dimensions first, then facts.
   ============================================================================= */
USE TelcoChurn;
GO
DECLARE @Root NVARCHAR(260) = N'C:\repos\telecom-churn-analytics\data\processed\';
DECLARE @sql  NVARCHAR(MAX);

DECLARE @tables TABLE (load_order INT, table_name SYSNAME, file_name NVARCHAR(100));
INSERT INTO @tables VALUES
    (1, N'dim_customer',          N'star\dim_customer.csv'),
    (2, N'dim_contract',          N'star\dim_contract.csv'),
    (3, N'dim_services',          N'star\dim_services.csv'),
    (4, N'dim_date',              N'star\dim_date.csv'),
    (5, N'fact_customer',         N'star\fact_customer.csv'),
    (6, N'fact_network_monthly',  N'star\fact_network_monthly.csv'),
    (7, N'dq_results',            N'dq_results.csv');

/* facts first: nothing references them, so TRUNCATE is allowed and it frees the dims for DELETE */
TRUNCATE TABLE dbo.fact_network_monthly;
TRUNCATE TABLE dbo.fact_customer;
TRUNCATE TABLE dbo.dq_results;

DECLARE @t SYSNAME, @f NVARCHAR(100);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR
    SELECT table_name, file_name FROM @tables ORDER BY load_order;
OPEN c;
FETCH NEXT FROM c INTO @t, @f;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = N'TRUNCATE TABLE dbo.' + QUOTENAME(@t) + N';';
    -- fact tables reference dims, so TRUNCATE is only allowed when no FK points at the table
    IF @t LIKE N'dim_%' SET @sql = N'DELETE FROM dbo.' + QUOTENAME(@t) + N';';
    EXEC sp_executesql @sql;

    SET @sql = N'BULK INSERT dbo.' + QUOTENAME(@t) + N'
                 FROM ''' + @Root + @f + N'''
                 WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','',
                       ROWTERMINATOR = ''0x0a'', CODEPAGE = ''65001'', TABLOCK, KEEPNULLS);';
    EXEC sp_executesql @sql;
    PRINT CONCAT('Loaded ', @t, ' from ', @f);
    FETCH NEXT FROM c INTO @t, @f;
END
CLOSE c; DEALLOCATE c;

/* Reconciliation: facts must match dimension coverage ------------------------ */
SELECT 'dim_customer' AS tbl, COUNT(*) AS rows_ FROM dbo.dim_customer
UNION ALL SELECT 'fact_customer',        COUNT(*) FROM dbo.fact_customer
UNION ALL SELECT 'fact_network_monthly', COUNT(*) FROM dbo.fact_network_monthly
UNION ALL SELECT 'orphan_network_rows',  COUNT(*) FROM dbo.fact_network_monthly n
                                           LEFT JOIN dbo.dim_customer d ON d.customer_key = n.customer_key
                                           WHERE d.customer_key IS NULL;
GO
