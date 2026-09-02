# 0002: Bronze tables are pre-seeded fixtures, not produced by a taught EL step

## Status
Accepted

## Context
dbt does not perform extraction/load — it transforms tables that already exist in the warehouse. A realistic pipeline needs bronze data to come from somewhere: either a real EL step (e.g. an Airflow task extracting from the course's seed Postgres into BigQuery bronze tables), or fixtures loaded once as environment setup.

Building a real EL step means teaching ingestion patterns (incremental loads, schema drift, CDC-adjacent concerns) that are a distinct skill from what this course is about (orchestration and transformation on GKE). The course already spans Airflow, Kubernetes, dbt, and BigQuery — adding EL as a taught concept risks diluting the module past what's learnable in one sitting.

## Decision
Bronze tables (`sales.raw_orders`, `sales.raw_customers`, `marketing.raw_campaigns`, `marketing.raw_leads`) are loaded directly into BigQuery as one-time setup fixtures (via `dbt seed` or a setup-script `bq load`), representing "two source systems that have already landed." The Airflow DAG built in this course starts at bronze and never performs extraction.

## Consequences
- The exercise stays scoped to orchestration + transformation, not ingestion — consistent with the course's stated goal.
- The pipeline is not end-to-end from real source systems; a learner who wants the full extract-to-mart picture needs a separate ingestion-focused module (not built here).
- If a future module is added that does teach EL, it can slot in *before* this course's Exercise 3 (seed bronze) without changing anything downstream — bronze's shape is fixed regardless of how it's produced.
