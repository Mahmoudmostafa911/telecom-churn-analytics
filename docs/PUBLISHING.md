# Publishing checklist

## 1. Run on the real data (5 minutes)

```powershell
cd telecom-churn-analytics
pip install -r requirements.txt
python data/download_data.py
python data/generate_network_kpis.py
$env:PYTHONPATH = "src"; python -m telco_churn run
python -m pytest tests -q
```

This replaces the committed `docs/findings.md`, `docs/img/*.png`, `model/*.csv|json` and
`data/processed/**` (which were produced from the synthetic fixture) with real-data results.
Open `docs/findings.md` and copy the exact numbers into the README "What the analysis shows"
table and into `linkedin/posts.md` where you see `[brackets]`.

## 2. GitHub

* Create the repo `Mahmoudmostafa911/telecom-churn-analytics` (public) and push the folder
  (`git init && git add . && git commit -m "Telecom churn & network quality analytics" && git push`).
  Pushing from your own machine avoids the flattened-folder problem we hit with drag-and-drop upload.
* **About / description (≤ 350 chars):**
  `End-to-end telecom churn analytics on the IBM Telco dataset: Python cleaning + ~45-rule quality gate, Kimball star schema (SQLite/SQL Server), portable analytics SQL, interpretable churn model with gain chart, Power BI model & DAX. CI-tested.`
* **Topics:** `data-engineering` `data-analytics` `churn-prediction` `telecom` `python` `pandas`
  `sql` `sql-server` `t-sql` `power-bi` `dax` `star-schema` `data-quality` `scikit-learn` `github-actions`
* Pin the repo (you have 6 pin slots; this becomes the 5th).
* Profile README `Mahmoudmostafa911/Mahmoudmostafa911/README.md` → add a row to the Featured Projects table:

  `| [Telecom Churn & Network Quality Analytics](https://github.com/Mahmoudmostafa911/telecom-churn-analytics) | Production-style churn pipeline on real IBM data: schema contract, quality gate with audit table, star schema for SQL Server/Power BI, portable SQL, interpretable model with gain chart, CI | Python · pandas · T-SQL · Power BI · DAX · scikit-learn · GitHub Actions |`

* Check the Actions tab — the CI badge in the README turns green after the first push.

## 3. LinkedIn

* **Featured → Add a link** to the repo. Title/description are in `linkedin/posts.md`.
* **Projects → Add**: name, description, 5 skills and the repo as media (texts in `linkedin/posts.md`).
  Tick "currently working on this", start date = this month, no company association.
* Post 1 (architecture image) this week; posts 2 and 3 in the following two weeks.
  Put the repo link in the first comment.

## 4. Optional upgrades that recruiters notice

1. Build the `.pbix` from `model/report_layout.md`, screenshot the five pages into `docs/img/pbi_page_N.png`,
   replace the TODO in the README.
2. Load the star into SQL Server with `sql/sqlserver/01…04` and add a screenshot of `08_risk_segments.sql`
   running in SSMS.
3. Fabric variant: upload `data/processed/star/*.csv` to a Lakehouse, load to Delta tables, build a Direct
   Lake model — then the DP-600/DP-700 mapping table in the README becomes a demo, not a claim.
