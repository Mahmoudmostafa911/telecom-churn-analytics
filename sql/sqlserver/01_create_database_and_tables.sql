/* =============================================================================
   Telecom Churn & Network Quality Analytics  —  SQL Server DDL
   Creates the star schema produced by the Python pipeline so that the
   portable queries in sql/analytics/*.sql run unchanged in SSMS.
   Tested against SQL Server 2019+/Azure SQL syntax.
   ============================================================================= */
IF DB_ID(N'TelcoChurn') IS NULL
    CREATE DATABASE TelcoChurn;
GO
USE TelcoChurn;
GO

/* ---------- dimensions ---------------------------------------------------- */
IF OBJECT_ID('dbo.dim_customer') IS NOT NULL DROP TABLE dbo.dim_customer;
CREATE TABLE dbo.dim_customer (
    customer_key     INT           NOT NULL CONSTRAINT PK_dim_customer PRIMARY KEY,
    customer_id      VARCHAR(20)   NOT NULL CONSTRAINT UQ_dim_customer_id UNIQUE,
    gender           VARCHAR(10)   NOT NULL,
    senior_citizen   VARCHAR(3)    NOT NULL,
    partner          VARCHAR(3)    NOT NULL,
    dependents       VARCHAR(3)    NOT NULL,
    tenure_months    TINYINT       NOT NULL,
    tenure_bucket    VARCHAR(20)   NOT NULL
);

IF OBJECT_ID('dbo.dim_contract') IS NOT NULL DROP TABLE dbo.dim_contract;
CREATE TABLE dbo.dim_contract (
    contract_key      INT          NOT NULL CONSTRAINT PK_dim_contract PRIMARY KEY,
    contract          VARCHAR(20)  NOT NULL,
    paperless_billing VARCHAR(3)   NOT NULL,
    payment_method    VARCHAR(40)  NOT NULL,
    is_auto_payment   BIT          NOT NULL
);

IF OBJECT_ID('dbo.dim_services') IS NOT NULL DROP TABLE dbo.dim_services;
CREATE TABLE dbo.dim_services (
    services_key        INT          NOT NULL CONSTRAINT PK_dim_services PRIMARY KEY,
    phone_service       VARCHAR(3)   NOT NULL,
    multiple_lines      VARCHAR(20)  NOT NULL,
    internet_service    VARCHAR(15)  NOT NULL,
    online_security     VARCHAR(20)  NOT NULL,
    online_backup       VARCHAR(20)  NOT NULL,
    device_protection   VARCHAR(20)  NOT NULL,
    tech_support        VARCHAR(20)  NOT NULL,
    streaming_tv        VARCHAR(20)  NOT NULL,
    streaming_movies    VARCHAR(20)  NOT NULL,
    num_addon_services  TINYINT      NOT NULL,
    has_internet        BIT          NOT NULL,
    has_phone           BIT          NOT NULL,
    has_streaming       BIT          NOT NULL
);

IF OBJECT_ID('dbo.dim_date') IS NOT NULL DROP TABLE dbo.dim_date;
CREATE TABLE dbo.dim_date (
    month_key               INT         NOT NULL CONSTRAINT PK_dim_date PRIMARY KEY,   -- yyyymm
    month                   CHAR(7)     NOT NULL,                                       -- 'YYYY-MM'
    year                    SMALLINT    NOT NULL,
    month_number            TINYINT     NOT NULL,
    month_name              CHAR(3)     NOT NULL,
    quarter                 CHAR(2)     NOT NULL,
    month_start_date        DATE        NOT NULL,
    month_index             TINYINT     NOT NULL,   -- 1 = oldest, 12 = snapshot month
    months_before_snapshot  TINYINT     NOT NULL
);

/* ---------- facts ------------------------------------------------------------ */
IF OBJECT_ID('dbo.fact_customer') IS NOT NULL DROP TABLE dbo.fact_customer;
CREATE TABLE dbo.fact_customer (
    customer_key             INT            NOT NULL CONSTRAINT PK_fact_customer PRIMARY KEY,
    contract_key             INT            NOT NULL,
    services_key             INT            NOT NULL,
    customer_id              VARCHAR(20)    NOT NULL,
    monthly_charges          DECIMAL(9,2)   NOT NULL,
    total_charges            DECIMAL(11,2)  NOT NULL,
    lifetime_avg_monthly     DECIMAL(9,2)   NULL,
    charge_ratio             DECIMAL(9,3)   NULL,
    revenue_band             VARCHAR(10)    NULL,
    churn                    VARCHAR(3)     NOT NULL,
    churn_flag               BIT            NOT NULL,
    kpi_months               TINYINT        NOT NULL CONSTRAINT DF_fact_customer_kpi DEFAULT 0,
    avg_dropped_call_pct     DECIMAL(9,3)   NULL,
    avg_download_mbps        DECIMAL(9,2)   NULL,
    avg_latency_ms           DECIMAL(9,2)   NULL,
    total_outage_minutes     INT            NULL,
    avg_data_usage_gb        DECIMAL(9,2)   NULL,
    network_complaints       INT            NULL,
    l3m_dropped_call_pct     DECIMAL(9,3)   NULL,
    l3m_download_mbps        DECIMAL(9,2)   NULL,
    l3m_latency_ms           DECIMAL(9,2)   NULL,
    l3m_outage_minutes       INT            NULL,
    l3m_complaints           INT            NULL,
    dropped_call_trend_pp    DECIMAL(9,3)   NULL,
    latency_trend_pct        DECIMAL(9,1)   NULL,
    download_trend_pct       DECIMAL(9,1)   NULL,
    network_quality_score    DECIMAL(5,1)   NULL,
    network_quality_band     VARCHAR(15)    NULL,
    churn_probability        DECIMAL(6,4)   NULL,
    risk_band                VARCHAR(10)    NULL,
    CONSTRAINT FK_fact_customer_customer FOREIGN KEY (customer_key) REFERENCES dbo.dim_customer(customer_key),
    CONSTRAINT FK_fact_customer_contract FOREIGN KEY (contract_key) REFERENCES dbo.dim_contract(contract_key),
    CONSTRAINT FK_fact_customer_services FOREIGN KEY (services_key) REFERENCES dbo.dim_services(services_key)
);
CREATE INDEX IX_fact_customer_contract ON dbo.fact_customer(contract_key);
CREATE INDEX IX_fact_customer_services ON dbo.fact_customer(services_key);

IF OBJECT_ID('dbo.fact_network_monthly') IS NOT NULL DROP TABLE dbo.fact_network_monthly;
CREATE TABLE dbo.fact_network_monthly (
    customer_key        INT            NOT NULL,
    month_key           INT            NOT NULL,
    customer_id         VARCHAR(20)    NOT NULL,
    month               CHAR(7)        NOT NULL,
    month_index         TINYINT        NOT NULL,
    dropped_call_pct    DECIMAL(9,3)   NULL,
    avg_download_mbps   DECIMAL(9,1)   NULL,
    avg_latency_ms      DECIMAL(9,1)   NULL,
    outage_minutes      INT            NOT NULL,
    data_usage_gb       DECIMAL(9,1)   NULL,
    complaints          TINYINT        NOT NULL,
    CONSTRAINT PK_fact_network_monthly PRIMARY KEY (customer_key, month_key),
    CONSTRAINT FK_fnm_customer FOREIGN KEY (customer_key) REFERENCES dbo.dim_customer(customer_key),
    CONSTRAINT FK_fnm_date     FOREIGN KEY (month_key)    REFERENCES dbo.dim_date(month_key)
);
CREATE INDEX IX_fnm_month ON dbo.fact_network_monthly(month_key) INCLUDE (dropped_call_pct, avg_latency_ms);

/* ---------- audit / metadata -------------------------------------------------- */
IF OBJECT_ID('dbo.dq_results') IS NOT NULL DROP TABLE dbo.dq_results;
CREATE TABLE dbo.dq_results (
    run_ts       CHAR(20)       NOT NULL,
    check_name   VARCHAR(80)    NOT NULL,
    [table]      VARCHAR(40)    NOT NULL,
    status       VARCHAR(5)     NOT NULL,
    observed     VARCHAR(100)   NULL,
    expectation  VARCHAR(400)   NULL,
    details      VARCHAR(400)   NULL
);
GO
