# Context: Data Pipeline on GKE

A standalone course (sibling to `../gke_essentials/`) teaching dbt + Airflow orchestration deployed on GKE. Assumes GKE fundamentals are already known (`enterprise_course`/`exercises` or `gke_essentials`); this course starts at real infrastructure, no local `kind` warm-up stage.

## Glossary

**Bronze / Staging** — Raw source tables, one-to-one with the source system, landed in BigQuery. In dbt terms this is the `staging` layer: `stg_<source>__<entity>.sql`, light cleanup only (renames, casts), no cross-source joins. Materialized as `view`. For this course, bronze is **pre-seeded as fixtures** (not produced by a taught EL step) — see `docs/adr/0002-preseeded-bronze-fixtures.md`.

**Silver / Intermediate** — Business-logic transforms and cross-source joins, grouped by domain folder (e.g. `models/intermediate/sales/`). Prefixed `int_`. Materialized `ephemeral` by default (reconsider `table` if fanned out to many downstream marts).

**Gold / Marts** — Consumer-facing, one model per business entity (e.g. `customers`, `customer_360`). Materialized as `table`.

**Domain** — A grouping of related source tables and downstream models that share a business area and, in this course, share an orchestration unit (one Cosmos/Kubernetes task group per domain) and can carry a distinct GCP service account. This course uses two domains: `sales` and `marketing`.

**Domain-grouped orchestration** — The chosen granularity for Airflow tasks: one task (and one pod, via Cosmos's `kubernetes` execution mode) builds all intermediate + mart models for a given domain, rather than one pod per individual dbt model. See `docs/adr/0003-domain-grouped-orchestration.md`.

**Cross-domain group** — `customer_360` depends on both `sales` and `marketing` intermediate models, so it can't belong to either domain's task group. It lives in its own `models/marts/cross_domain/` path and its own Airflow task group, scheduled downstream of *both* domain groups (`sales_group >> cross_domain_group`, `marketing_group >> cross_domain_group`). This is why marts are split into `marts/sales/`, `marts/marketing/`, `marts/cross_domain/` rather than one flat `marts/` folder — Cosmos selects each task group by path, and path-based selection needs the domain boundary to exist on disk.

## Dataset scope (this course's exercise data)

- `sales` domain — bronze: `raw_orders`, `raw_customers`. 
- `marketing` domain — bronze: `raw_campaigns`, `raw_leads`.
- Silver: one `int_` model per domain.
- Gold: 2-3 marts, including at least one cross-domain mart (e.g. `customer_360`) to make the domain split meaningful without over-scoping into a full data-modeling exercise.

## Architecture decisions

- Airflow deployed self-managed via the official Helm chart (not Cloud Composer) — `docs/adr/0001-self-managed-airflow-helm.md`
- Bronze tables are pre-seeded fixtures, not produced by a taught EL step — `docs/adr/0002-preseeded-bronze-fixtures.md`
- Orchestration granularity is domain-grouped (Cosmos, `kubernetes` execution mode), not per-model — `docs/adr/0003-domain-grouped-orchestration.md`
- Warehouse target is BigQuery (dbt-bigquery adapter), not Postgres-in-place — realistic OLTP/OLAP split, reuses Workload Identity already taught in `enterprise_course` module 19.

## Course shell

Directory: `data_pipeline_on_gke/` (sibling to `gke_essentials/`).

1. Provision the pipeline cluster & BigQuery datasets
2. Deploy Airflow via Helm
3. Seed bronze
4. Build the dbt project (staging → intermediate → marts, run locally with `dbt build` before touching orchestration)
5. Wire up Cosmos + KubernetesPodOperator, domain-grouped
6. Operate it (trigger a run, watch pods get scheduled, debug via isolated per-domain pod logs)
