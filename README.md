# Data Pipeline on GKE

A short course on orchestrating dbt with Airflow, deployed on GKE. Where `../gke_essentials/` teaches the GKE loop itself (write/apply/verify/operate a manifest), this course assumes that loop is already second nature and spends its six exercises on the next layer up: a real bronze → silver → gold data pipeline, with Airflow's KubernetesExecutor spinning up a dedicated pod per domain to run dbt against BigQuery.

See [`CONTEXT.md`](CONTEXT.md) for the glossary (bronze/silver/gold, domain, domain-grouped orchestration) and [`docs/adr/`](docs/adr/) for the trade-offs behind the three biggest calls this course makes: self-managed Airflow over Cloud Composer, pre-seeded bronze fixtures over a taught EL step, and domain-grouped (not per-model) pod orchestration.

## Course map

| # | Exercise | Where it runs |
|---|---|---|
| 01 | [Provisioning the Pipeline Cluster & BigQuery](01_provisioning_the_pipeline_cluster.md) | GKE + BigQuery |
| 02 | [Deploying Airflow with Helm](02_deploying_airflow_with_helm.md) | GKE |
| 03 | [Seeding Bronze](03_seeding_bronze.md) | BigQuery |
| 04 | [Building the dbt Project](04_building_the_dbt_project.md) | local, against BigQuery |
| 05 | [Orchestrating with Cosmos](05_orchestrating_with_cosmos.md) | GKE |
| 06 | [Operating & Debugging the Pipeline](06_operating_and_debugging.md) | GKE |

## What you'll build

Two source domains — `sales` and `marketing` — land as bronze fixtures in BigQuery. A dbt project transforms each domain independently through staging (bronze) and intermediate (silver) models into per-domain marts (gold), plus one cross-domain mart, `customer_360`, that only builds once both domains are done. Airflow, running on GKE via the official Helm chart, triggers this daily: one Kubernetes pod per domain runs `dbt build` for that domain's slice of the DAG, and a third pod builds the cross-domain mart once both finish.

```
bronze (BigQuery, pre-seeded)
  sales:      raw_orders, raw_customers
  marketing:  raw_campaigns, raw_leads
       |
       v  (dbt staging models, one pod per domain)
silver (dbt intermediate models)
       |
       v
gold (dbt marts)
  sales:        sales_summary
  marketing:    marketing_summary
  cross_domain: customer_360  <- needs both domains done first
```

## Prerequisites
- Complete `../gke_essentials/` or `../enterprise_course/` + `../exercises/` first — this course does not re-teach `kubectl`, Deployments, Services, or Helm basics.
- `kubectl`, `helm`, `dbt` (with the `dbt-bigquery` adapter) installed locally
- `gcloud`, authenticated, with a billing-enabled GCP project and the BigQuery API enabled
- `git` remote to push this repo to (for Airflow's `dags.gitSync`, Exercise 02)

## Setup
```bash
cd data_pipeline_on_gke

export GCP_PROJECT_ID=your-project-id
gcloud config set project "$GCP_PROJECT_ID"
gcloud services enable container.googleapis.com bigquery.googleapis.com

# ... work through exercises 01-06 ...

gcloud container clusters delete data-pipeline --region europe-west1 --project "$GCP_PROJECT_ID"
```

Each command is explained in context the first time it appears — see [Exercise 01](01_provisioning_the_pipeline_cluster.md).
