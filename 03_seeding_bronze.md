# Exercise 03: Seeding Bronze

## What you'll build
The four bronze tables — `gke_bronze.raw_orders`, `gke_bronze.raw_customers`, `gke_bronze.raw_campaigns`, `gke_bronze.raw_leads` — loaded into BigQuery from the fixture CSVs in `dbt/pipeline/seeds/`.

## Concepts covered
- `dbt seed`: loads CSVs straight into the warehouse as tables, matched one-to-one by filename. It's a dbt command, not a dbt *model* — seeds aren't transformed, just loaded verbatim
- Why bronze isn't built by this course: see [`docs/adr/0002-preseeded-bronze-fixtures.md`](docs/adr/0002-preseeded-bronze-fixtures.md) — a real EL step is a different skill from orchestration/transformation, which is what this course teaches

## Why this matters
Every exercise from here on assumes bronze already exists and only asks "how do we transform it." That's a deliberate simplification, not an accident: pretending a `dbt seed` command is a production ingestion pipeline would be misleading, so this exercise names the fixture data for what it is — pre-landed source-system data standing in for a real EL job.

## Prerequisites
- Exercise 01 complete (the `gke_bronze` dataset exists)
- `dbt-bigquery` installed locally: `pip install dbt-bigquery`
- `gcloud auth application-default login` run locally (dbt's `method: oauth` uses your local ADC when run outside the cluster; Exercise 05 switches this to the pod's Workload Identity ADC instead — same `profiles.yml`, same auth method, different credential source)

## Steps

### 1. Point dbt at your project
```bash
cd dbt/pipeline
export DBT_PROFILES_DIR=..
export GCP_PROJECT_ID=your-project-id
```

### 2. Load the fixtures
```bash
dbt seed
```
This creates four tables in the `gke_bronze` dataset — the custom `generate_schema_name` macro (`dbt/pipeline/macros/generate_schema_name.sql`) is why they land in `gke_bronze` directly instead of a dbt-suffixed dataset like `gke_silver_gke_bronze`.

### 3. Confirm the row counts match the CSVs
```bash
bq query --use_legacy_sql=false \
  "SELECT table_name, row_count FROM \`${GCP_PROJECT_ID}.gke_bronze.__TABLES__\` ORDER BY table_name"
```

## Verify
**In the Console:** [BigQuery](https://console.cloud.google.com/bigquery) → expand `gke_bronze` → four tables, each with a **Preview** tab showing rows matching the corresponding CSV in `dbt/pipeline/seeds/`.

**On the CLI:**
```bash
bq show --format=prettyjson "${GCP_PROJECT_ID}:gke_bronze.raw_orders" | grep numRows
# expect "8"
```
Re-running `dbt seed` is safe — it truncates and reloads each table, so it always matches the CSVs exactly regardless of how many times you run it.
