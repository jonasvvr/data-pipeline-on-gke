# 0003: Domain-grouped orchestration granularity (Cosmos, Kubernetes execution mode, one pod per domain)

## Status
Accepted

## Context
Airflow can invoke dbt at several granularities:
- A single `KubernetesPodOperator` task running `dbt build` for the whole project (one pod total). Matches dbt's own guidance ("it's not recommended to have a dbt job for every single node in your DAG") but gives no per-model or per-domain isolation, retry granularity, or per-domain service-account scoping.
- `BashOperator` running `dbt build` inside the Airflow worker image. Zero isolation; doesn't exercise GKE pod scheduling beyond hosting Airflow itself.
- Astronomer Cosmos, `kubernetes` execution mode, expanded to one Airflow task (and one pod) **per individual dbt model**. Maximum isolation and per-model retry/debugging, but multiplies pod-scheduling overhead (image pull + startup per model) across the whole project — costly at any real model count, and works against dbt's own "coarse-grained job" guidance for no compute benefit, since dbt-bigquery pushes actual compute down to BigQuery — the pod itself stays lightweight regardless of table size.

The dataset for this course spans two domains (`sales`, `marketing`) specifically so this decision has real stakes: with only one domain, domain-grouping would collapse to "one pod total" and not illustrate anything.

## Decision
Use Cosmos with the `kubernetes` execution mode, but group Airflow tasks (and therefore pods) by **domain**, not by individual model: one pod builds all `sales` intermediate + mart models, another builds all `marketing` intermediate + mart models.

## Consequences
- Captures the two genuine benefits of pod-per-task (isolated debugging/logs; the ability to bind a different GCP service account per domain via Workload Identity) without paying per-model pod-scheduling overhead.
- Retrying a single failed *model* still requires re-running its whole domain group, not just that model — a real trade-off against full per-model granularity. Acceptable at this course's scale (2 domains, single-digit models per domain); would need revisiting if a domain grows to dozens of models with meaningfully different SLAs.
- "Appropriate compute per task" is not the driving justification here (see Context) — sizing pods is not very useful when BigQuery does the actual transformation compute. Anyone extending this pattern to a non-pushdown adapter (e.g. dbt running against Spark/DuckDB in-pod) should re-evaluate whether compute sizing becomes a stronger factor.
