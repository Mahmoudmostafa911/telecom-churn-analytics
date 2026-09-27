"""telco_churn — Telecom Churn & Network Quality Analytics pipeline.

End-to-end, dependency-light analytics pipeline:

    raw CSVs  ->  clean  ->  features  ->  quality gate  ->  star schema (SQLite / SQL Server)
              ->  churn model  ->  charts + findings.md  ->  Power BI

Run everything with::

    python -m telco_churn run --raw data/raw/Telco-Customer-Churn.csv

See README.md for the full walkthrough.
"""

__version__ = "1.0.0"
__author__ = "Mahmoud Mostafa"
