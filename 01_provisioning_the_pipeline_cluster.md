# Exercise 01: Provisioning the Pipeline Cluster & BigQuery

## What you'll build
A GKE Autopilot cluster to run Airflow and the dbt pods it launches, three BigQuery datasets (`bronze`, `silver`, `gold`), and two Kubernetes ServiceAccounts bound via Workload Identity to two distinct GCP service accounts with two distinct levels of BigQuery access.

## Concepts covered
- BigQuery datasets as the unit of access control: bronze/silver/gold as three separate datasets, not three schemas bolted onto one
- Workload Identity Federation for GKE, applied twice, for two different blast radii: Airflow's own control-plane pods get *no* BigQuery access; the dbt pods get exactly the write access they need
- `iam.gke.io/gcp-service-account`: the KSA annotation that completes a Workload Identity binding (the GCP-side half is a `gcloud iam service-accounts add-iam-policy-binding` call, same shape as `enterprise_course` module 19)

## Why this matters
It's tempting to give one service account "BigQuery Admin" and move on. That means a bug in Airflow's scheduler — which never touches data, only schedules pods — has a path to modify or delete every table in the warehouse. Splitting the identity in two costs one extra `gcloud` command per exercise and removes that path entirely: `airflow-runner` genuinely cannot run a BigQuery query even if compromised, because it was never granted a role that lets it.

## Prerequisites
- `../gke_essentials/` or `../enterprise_course/` + `../exercises/` complete
- `export GCP_PROJECT_ID=your-project-id`

## Steps

### 1. Enable the required APIs and create the cluster
```bash
gcloud services enable container.googleapis.com bigquery.googleapis.com --project "$GCP_PROJECT_ID"

gcloud container clusters create-auto data-pipeline \
  --region europe-west1 \
  --project "$GCP_PROJECT_ID"

gcloud container clusters get-credentials data-pipeline --region europe-west1
```
Autopilot, same as `gke_essentials` — this course is about the pipeline, not node-pool tuning.

### 2. Create the namespace and the two KSAs
```bash
kubectl apply -f manifests/01-provision/namespace.yaml
kubectl apply -f manifests/01-provision/serviceaccounts.yaml
```
See the comment in `manifests/01-provision/serviceaccounts.yaml` for why there are two KSAs instead of one.

### 3. Create the BigQuery datasets
**In the Console:** [BigQuery](https://console.cloud.google.com/bigquery) → click your project → **Create dataset** three times, naming them `gke_bronze`, `gke_silver`, `gke_gold`, region `europe-west1` (must match the `location` in `dbt/pipeline/profiles.yml`).

Or on the CLI:
```bash
for dataset in gke_bronze gke_silver gke_gold; do
  bq mk --project_id="$GCP_PROJECT_ID" --location=europe-west1 "$dataset"
done
```

### 4. Create the two GCP service accounts and bind them via Workload Identity
```bash
gcloud iam service-accounts create airflow-runner --project "$GCP_PROJECT_ID"
gcloud iam service-accounts create dbt-runner --project "$GCP_PROJECT_ID"

# dbt-runner needs to write gke_silver/gke_gold and read gke_bronze
bq add-iam-policy-binding --member="serviceAccount:dbt-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/bigquery.dataEditor "${GCP_PROJECT_ID}:gke_silver"
bq add-iam-policy-binding --member="serviceAccount:dbt-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/bigquery.dataEditor "${GCP_PROJECT_ID}:gke_gold"
bq add-iam-policy-binding --member="serviceAccount:dbt-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/bigquery.dataViewer "${GCP_PROJECT_ID}:gke_bronze"
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:dbt-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/bigquery.jobUser

# airflow-runner gets nothing BigQuery-specific -- it only needs to exist as a workload identity
# principal so its pods can start; it never queries BigQuery itself.

for ksa_gsa in "airflow-runner:airflow-runner" "dbt-runner:dbt-runner"; do
  ksa="${ksa_gsa%%:*}"
  gsa="${ksa_gsa##*:}"
  gcloud iam service-accounts add-iam-policy-binding "${gsa}@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:${GCP_PROJECT_ID}.svc.id.goog[data-pipeline/${ksa}]"
  kubectl annotate serviceaccount "$ksa" -n data-pipeline \
    "iam.gke.io/gcp-service-account=${gsa}@${GCP_PROJECT_ID}.iam.gserviceaccount.com" --overwrite
done
```
This is the same pattern as `enterprise_course` module 19, applied twice: each `gcloud iam service-accounts add-iam-policy-binding` grants the *Kubernetes* principal (identified by namespace + KSA name, not a key file) permission to impersonate the *GCP* service account; the `kubectl annotate` tells GKE which GCP service account a pod running as that KSA should present as.

## Verify
**In the Console:**
- [Kubernetes Engine → Clusters](https://console.cloud.google.com/kubernetes/list) shows `data-pipeline`, status green.
- [BigQuery](https://console.cloud.google.com/bigquery) shows three datasets under your project: `gke_bronze`, `gke_silver`, `gke_gold`, all empty.
- [IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) shows `airflow-runner` and `dbt-runner`.

**On the CLI:**
```bash
kubectl get serviceaccount -n data-pipeline -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.annotations.iam\.gke\.io/gcp-service-account}{"\n"}{end}'
bq ls --project_id="$GCP_PROJECT_ID"
```
The first command should print both KSAs, each with its matching GCP service account email — an empty second column means the annotation didn't land and the binding won't work.
