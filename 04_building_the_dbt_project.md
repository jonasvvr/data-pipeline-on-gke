# Exercise 04: Building the dbt Project

## What you'll build
The full transform chain, run locally against BigQuery: staging views over bronze, intermediate models joining within each domain, and marts — including `customer_360`, the one model that joins across `sales` and `marketing`.

## Concepts covered
- **Staging** (`models/staging/`): one `stg_<source>__<entity>.sql` per bronze table, `source()` not `ref()`, light renames/casts only, materialized as `view`
- **Intermediate** (`models/intermediate/`): joins within a single domain, `ref()` everything, materialized `ephemeral` — meaning dbt inlines the model as a subquery wherever it's referenced, rather than persisting it as its own table/view
- **Marts** (`models/marts/`): consumer-facing, materialized as `table`. Split into `marts/sales/`, `marts/marketing/`, `marts/cross_domain/` — not one flat folder — because Exercise 05 selects each domain's models by path, and `customer_360` (in `cross_domain/`) depends on both domains so it can't live in either
- `dbt build`: runs models *and* tests *and* seeds in dependency order, in one command — the same command this course's Airflow pods will run in Exercise 05

## Why this matters
Running the whole project locally before wiring up Airflow means every SQL bug gets caught in a `dbt build` you can iterate on in seconds, not inside a Kubernetes pod whose logs you have to go fetch. Airflow will run the exact same `dbt build --select path:...` commands this exercise uses directly — Exercise 05 changes *who* runs them, not *what* runs.

## Prerequisites
- Exercise 03 complete (gke_bronze tables exist)
- `dbt/pipeline` set up as in Exercise 03 (`DBT_PROFILES_DIR`, `GCP_PROJECT_ID`, ADC logged in)

## Steps

### 1. Build the sales domain in isolation
```bash
cd dbt/pipeline
dbt build --select path:models/staging/sales path:models/intermediate/sales path:models/marts/sales
```
This is the exact selector Exercise 05's `sales` Cosmos task group uses. `int_sales__orders_joined` won't appear as its own object in BigQuery — it's ephemeral, so its SQL gets inlined directly into `sales_summary`'s query.

### 2. Build the marketing domain in isolation
```bash
dbt build --select path:models/staging/marketing path:models/intermediate/marketing path:models/marts/marketing
```

### 3. Build the cross-domain mart
```bash
dbt build --select path:models/marts/cross_domain
```
This only works because steps 1 and 2 already ran: `customer_360` references `sales_summary` (a real table, built in step 1) and re-inlines `int_marketing__leads_joined` (ephemeral, recompiled from `stg_marketing__leads`/`stg_marketing__campaigns`, which are views built in step 2). If you run this step before 1 and 2, it fails with a "table not found" error on `sales_summary` — a preview of exactly why Exercise 05's DAG makes `cross_domain` depend on both domain groups finishing first.

### 4. Inspect the compiled SQL for the ephemeral model
```bash
dbt compile --select int_sales__orders_joined
cat target/compiled/pipeline/models/intermediate/sales/int_sales__orders_joined.sql
```
Then look at the compiled `sales_summary.sql` in the same directory — the intermediate model's SQL is pasted in as a subquery rather than referenced by table name.

## Verify
**In the Console:** [BigQuery](https://console.cloud.google.com/bigquery) → `gke_silver` dataset shows 4 views (`stg_sales__orders`, `stg_sales__customers`, `stg_marketing__campaigns`, `stg_marketing__leads`) and no tables for the two `int_` models (they're ephemeral — nothing persists). `gke_gold` dataset shows 3 tables: `sales_summary`, `marketing_summary`, `customer_360`.

**On the CLI:**
```bash
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${GCP_PROJECT_ID}.gke_gold.customer_360\` ORDER BY customer_id"
```
Every row should have a non-null `acquisition_channel` except any customer who converted without a matching lead — check `dbt/pipeline/seeds/raw_leads.csv` against `raw_customers.csv` if a row looks wrong.

## Stretch goal
Add a `unique` + `not_null` test on `customer_id` in a new `models/marts/cross_domain/_cross_domain__models.yml`, then run `dbt build --select customer_360` again — `dbt build` runs tests immediately after the model they apply to, not as a separate pass, so a broken join fails the build right where it happened.
