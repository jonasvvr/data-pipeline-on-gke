# Exercise 02: Deploying Airflow with Helm

## What you'll build
Apache Airflow, running on the `data-pipeline` cluster, installed with the official Helm chart and configured for `KubernetesExecutor` — meaning every DAG task runs as its own pod rather than on a fixed pool of workers.

## Concepts covered
- The official Airflow Helm chart: same tool as `enterprise_course` module 13, a different chart
- `KubernetesExecutor`: the scheduler creates a new pod per task and tears it down when the task finishes, instead of routing tasks to long-running Celery workers. This is what makes "one pod per domain" (Exercise 05) possible at all — a Celery-based executor would run every task inside the same fixed worker pods
- `dags.gitSync`: the chart's built-in sidecar that polls a git repo and keeps `/opt/airflow/dags` in sync, so `kubectl apply`-ing a Helm upgrade is never how you ship a new DAG

## Why this matters
Airflow's scheduler, webserver, and triggerer are themselves long-running Deployments — this is the same "gains a feature each exercise" idea as `gke_essentials`' app, just applied to infrastructure instead of your own code: everything after this exercise assumes Airflow is already up and reachable.

## Prerequisites
- Exercise 01 complete (cluster, namespace, KSAs)
- This repo pushed to a git remote you can point `gitSync` at (a private fork is fine)
- `helm` installed locally

## Steps

### 1. Point `values.yaml` at your git remote
```bash
sed -i '' "s#PLACEHOLDER_GIT_REPO_URL#$(git remote get-url origin)#" airflow/values.yaml
```
`subPath: data_pipeline_on_gke/airflow/dags` is already set in `values.yaml` — gitSync clones the whole repo but Airflow only reads DAGs from that subdirectory.

### 2. Add the chart repo and install
```bash
helm repo add apache-airflow https://airflow.apache.org
helm repo update
helm search repo apache-airflow/airflow   # note the latest chart version, use it below

helm install airflow apache-airflow/airflow \
  --namespace data-pipeline \
  --values airflow/values.yaml \
  --version <chart-version-from-above>
```
This takes a few minutes — Postgres (Airflow's own metadata database, unrelated to BigQuery), the scheduler, webserver, and triggerer all need to come up.

### 3. Watch it come up
```bash
kubectl get pods -n data-pipeline -w
# Ctrl+C once everything shows Running / 1/1 or 2/2
```

### 4. Reach the webserver
```bash
kubectl port-forward -n data-pipeline svc/airflow-webserver 8080:8080 &
```
Open http://localhost:8080 (default credentials `admin` / the password Helm generated — retrieve it with the command the `helm install` output printed, or `kubectl get secret --namespace data-pipeline airflow-webserver-secret -o jsonpath="{.data.webserver-secret-key}" | base64 -d`).

## Verify
**In the Console:** [Kubernetes Engine → Workloads](https://console.cloud.google.com/kubernetes/workload) filtered to namespace `data-pipeline` shows `airflow-scheduler`, `airflow-webserver`, `airflow-triggerer`, and `airflow-postgresql` all healthy.

**On the CLI:**
```bash
kubectl get deploy -n data-pipeline
kubectl get pods -n data-pipeline -l component=scheduler
```
The DAGs list in the webserver UI will be empty until Exercise 05 adds `pipeline_dag.py` — an empty list here is expected, not a failure.
