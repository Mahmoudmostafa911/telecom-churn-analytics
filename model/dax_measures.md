# DAX measures

All measures live in a dedicated `_Measures` table. Formats: churn rates as `0.0%`,
money as `$#,##0`, scores as `0.0`.

## Base counts

```dax
Customers = COUNTROWS ( fact_customer )

Churned Customers = CALCULATE ( [Customers], fact_customer[churn_flag] = 1 )

Retained Customers = [Customers] - [Churned Customers]

Churn Rate = DIVIDE ( [Churned Customers], [Customers] )

Retention Rate = 1 - [Churn Rate]
```

## Revenue

```dax
Monthly Recurring Revenue = SUM ( fact_customer[monthly_charges] )

MRR Lost to Churn =
CALCULATE ( [Monthly Recurring Revenue], fact_customer[churn_flag] = 1 )

MRR Lost % = DIVIDE ( [MRR Lost to Churn], [Monthly Recurring Revenue] )

ARPU = DIVIDE ( [Monthly Recurring Revenue], [Customers] )

ARPU Churned =
CALCULATE ( [ARPU], fact_customer[churn_flag] = 1 )

Lifetime Revenue = SUM ( fact_customer[total_charges] )

Avg Tenure (months) = AVERAGE ( dim_customer[tenure_months] )
```

## Model-based risk

```dax
Avg Churn Probability = AVERAGE ( fact_customer[churn_probability] )

Expected MRR at Risk =
SUMX ( fact_customer, fact_customer[monthly_charges] * fact_customer[churn_probability] )

High Risk Customers =
CALCULATE ( [Customers], fact_customer[risk_band] = "High" )

High Risk Share = DIVIDE ( [High Risk Customers], [Customers] )

-- Lift of the selected segment vs the whole base (>1 = over-indexes on churn)
Churn Lift vs Base =
VAR BaseRate = CALCULATE ( [Churn Rate], REMOVEFILTERS ( ) )
RETURN DIVIDE ( [Churn Rate], BaseRate )

-- How many of all churners sit in the selected segment
Share of All Churn =
DIVIDE ( [Churned Customers], CALCULATE ( [Churned Customers], REMOVEFILTERS ( ) ) )
```

## Network quality (synthetic telemetry — label the visuals)

```dax
Avg Network Quality Score = AVERAGE ( fact_customer[network_quality_score] )

Avg Dropped Call % = AVERAGE ( fact_network_monthly[dropped_call_pct] )

Avg Latency (ms) = AVERAGE ( fact_network_monthly[avg_latency_ms] )

Avg Download (Mbps) = AVERAGE ( fact_network_monthly[avg_download_mbps] )

Outage Minutes = SUM ( fact_network_monthly[outage_minutes] )

Complaints = SUM ( fact_network_monthly[complaints] )

Complaints per 1k Customer-Months =
DIVIDE ( [Complaints], COUNTROWS ( fact_network_monthly ) ) * 1000

-- Same KPI for churned vs retained side by side on one chart
Avg Latency – Churned =
CALCULATE ( [Avg Latency (ms)], fact_customer[churn_flag] = 1 )

Avg Latency – Retained =
CALCULATE ( [Avg Latency (ms)], fact_customer[churn_flag] = 0 )

-- Change of the last 3 months vs the first 9 of the window (positive = worse)
Latency Trend % =
VAR Recent  = CALCULATE ( [Avg Latency (ms)], dim_date[months_before_snapshot] < 3 )
VAR Earlier = CALCULATE ( [Avg Latency (ms)], dim_date[months_before_snapshot] >= 3 )
RETURN DIVIDE ( Recent - Earlier, Earlier )
```

## Time intelligence on the monthly fact

```dax
Outage Minutes MoM % =
VAR Curr = [Outage Minutes]
VAR Prev = CALCULATE ( [Outage Minutes], DATEADD ( dim_date[month_start_date], -1, MONTH ) )
RETURN DIVIDE ( Curr - Prev, Prev )

Outage Minutes Rolling 3M =
CALCULATE ( [Outage Minutes],
            DATESINPERIOD ( dim_date[month_start_date], MAX ( dim_date[month_start_date] ), -3, MONTH ) )
```

## Data-quality tile

```dax
DQ Checks Passed =
CALCULATE ( COUNTROWS ( dq_results ), dq_results[status] = "PASS" )

DQ Checks Total = COUNTROWS ( dq_results )

DQ Pass Rate = DIVIDE ( [DQ Checks Passed], [DQ Checks Total] )

DQ Status Label =
IF ( CALCULATE ( COUNTROWS ( dq_results ), dq_results[status] = "FAIL" ) > 0,
     "❌ FAIL", IF ( CALCULATE ( COUNTROWS ( dq_results ), dq_results[status] = "WARN" ) > 0,
     "⚠ WARN", "✅ PASS" ) )
```

## Calculated columns (only where a slicer needs it)

```dax
-- dim_customer
Tenure Bucket Sort =
SWITCH ( dim_customer[tenure_bucket],
         "00-12 months", 1, "13-24 months", 2, "25-48 months", 3, "49-72 months", 4 )

-- fact_customer
Risk Band Sort = SWITCH ( fact_customer[risk_band], "High", 1, "Medium", 2, "Low", 3 )
```

Set *Sort by column* on `tenure_bucket` → `Tenure Bucket Sort` and `risk_band` → `Risk Band Sort`.
