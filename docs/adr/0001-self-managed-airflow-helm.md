# 0001: Self-managed Airflow via Helm chart, not Cloud Composer

## Status
Accepted

## Context
Airflow needs to run on GCP. Cloud Composer is GCP's managed Airflow offering and is what most enterprises actually run in production — it runs on GKE internally but hides cluster provisioning, Helm installation, and scheduler/webserver management from the operator. The official Airflow Helm chart is the alternative: you provision the GKE cluster yourself and install Airflow onto it directly, using the KubernetesExecutor.

This course's explicit premise is "orchestrated by Airflow and deployed on GKE" — the GKE deployment itself is a teaching objective, not incidental infrastructure.

## Decision
Deploy Airflow self-managed via the official Helm chart onto a GKE cluster the learner provisions themselves.

## Consequences
- Every component (scheduler pod, KubernetesExecutor-spawned worker pods, Cosmos-spawned dbt pods) is directly visible and `kubectl`-inspectable, reinforcing this repo's existing Helm (`enterprise_course` module 13) and Workload Identity (module 19) content.
- The learner takes on operational burden Cloud Composer would otherwise absorb (upgrades, HA configuration, chart values tuning) — acceptable here because operating Airflow on Kubernetes *is* the lesson.
- This choice is enterprise-realistic but not the enterprise-default: production teams reaching for "least operational overhead" would typically choose Composer instead. Switching later means re-learning the deployment model, not just changing a config value.
