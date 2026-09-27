# LinkedIn post series — Telecom Churn & Network Quality Analytics

Three posts, one week apart. Rules that worked on your own analytics: native image
(never a bare link), a story opener, one concrete lesson, question at the end, reply to
every comment in the first hour. Post the repo link in the **first comment**, not the body.

Replace anything in `[brackets]` with the numbers from **your** `docs/findings.md`
after running on the real data.

---

## Post 1 — the launch (attach `docs/img/architecture.png`)

**Hook (first two lines are all people see):**

I spent a weekend building the churn pipeline I wish I had at my first analytics job.

Not a notebook. A pipeline.

**Body:**

The data is public (IBM Telco, 7,043 customers). The question is the one every telecom asks: who is about to leave, why, and what does it cost?

What I built:

→ A schema contract: 21 columns checked one by one before anything runs
→ A cleaning step that logs what it fixed (11 blank TotalCharges cells — all tenure-0 customers — imputed, counted, reported)
→ A quality gate: ~45 rule checks that write an audit table and stop the run on FAIL
→ A star schema (4 dimensions, 2 facts) that loads to SQLite or SQL Server
→ 8 analytics queries written once in portable SQL — same file runs in SSMS and in the pipeline
→ A logistic-regression churn model with an odds-ratio driver table and a gain chart
→ 23 unit tests + GitHub Actions running the whole pipeline on every push

One design choice I'm proud of: the network telemetry is synthetic, and the project says so everywhere — file names, chart titles, model report. Portfolio projects don't need to pretend.

The headline finding on the real data: contract type beats everything. Month-to-month customers churn at ~[43]%, two-year at ~[3]%. Everything else is detail around that.

Repo in the first comment. Which part would you want a walkthrough on — the quality gate, the SQL, or the model?

#DataEngineering #Analytics #SQL #PowerBI #Python #Telecom #Churn

---

## Post 2 — the lesson (attach `docs/img/churn_drivers_customer.png`)

**Hook:**

Fiber-optic customers churn at 42%. DSL customers at 19%.

The obvious conclusion is wrong.

**Body:**

When I first ran the numbers on the IBM Telco dataset I almost wrote "fiber has a quality problem".

Then I looked at what else fiber customers have in common:

→ They pay ~$90/month vs ~$58 for DSL
→ They are far more likely to be on month-to-month contracts
→ They are far more likely to pay by electronic check

Put those into one logistic regression and the picture changes. Contract type is the strongest driver by a distance (two-year contract odds ratio ≈ [0.08]). Fiber is still a risk flag — but it looks like a price-and-commitment problem, not a network problem.

This matters for the retention budget. "Fix the fiber network" and "move fiber customers to annual contracts with auto-pay" are very different projects.

Three habits that saved me from the wrong headline:

1. Never report a segment's churn rate without the segment's other attributes next to it
2. Fit one interpretable model before any fancy one — coefficients are a conversation starter with the business
3. Keep an honest benchmark: my "real columns only" model is the number I quote; the model with synthetic telemetry is labelled illustrative

Full analysis + SQL in the repo (first comment).

What's a "wrong obvious conclusion" you've caught in your data?

#DataAnalytics #Churn #SQL #Python #PowerBI #Telecom

---

## Post 3 — the how-to (attach `docs/img/gain_chart_customer.png` or a screenshot of `dq_results.csv`)

**Hook:**

A retention team can't call 7,000 customers.

They can call 700. Which 700?

**Body:**

That is the only question a churn model needs to answer, and the gain chart answers it in one line:

Rank customers by predicted risk. The top [30]% contain ~[70]% of the people who actually churned.

So the practical output of the project isn't an AUC. It's a table:

customer_id · contract · tenure · monthly charges · churn probability · risk band

…sorted by probability, refreshed by a MERGE statement into the warehouse, and exposed to Power BI as a drill-through page the retention team can export.

How the scoring step is wired:

→ Stratified 75/25 split, standardised numerics, one-hot categoricals
→ Logistic regression as the primary model (interpretable), gradient boosting as the benchmark
→ Threshold chosen by best F1 (≈[0.26]), not the default 0.5 — retention teams prefer recall
→ Probability → risk band (Low < 0.20 ≤ Medium < 0.50 ≤ High) stored on the fact table
→ `MERGE` refresh in T-SQL so the scores update without reloading the star schema

Small detail I liked: scikit-learn is optional. If it isn't installed, a 40-line NumPy Newton–Raphson logistic regression takes over, so the pipeline still runs in a locked-down CI runner.

Repo in the first comment — the SQL Server scripts and DAX measures are in there too.

If you had to pick ONE metric to explain a churn model to a COO, which would it be?

#DataScience #Analytics #SQL #PowerBI #Python #MachineLearning

---

## First-comment template (all three posts)

Repo: https://github.com/Mahmoudmostafa911/telecom-churn-analytics
Dataset: IBM Telco Customer Churn (public). Network telemetry in the project is synthetic and labelled as such.

## Featured / Project entry texts

**LinkedIn Featured title:** Telecom Churn & Network Quality Analytics — Python, SQL & Power BI

**Description (≤ 300 chars):** End-to-end churn pipeline on the IBM Telco dataset: schema contract, ~45-rule quality gate, star schema for SQLite/SQL Server, portable analytics SQL, interpretable churn model with gain chart, Power BI model + DAX. Tested with CI.

**LinkedIn Project name:** Telecom Churn & Network Quality Analytics

**Skills to tag (5):** Python (pandas) · SQL (T-SQL) · Power BI · Data Modeling · Data Quality
