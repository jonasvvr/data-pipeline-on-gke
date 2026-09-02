# Exercise 05: Orchestrating with Cosmos

## What you'll build
The `bronze_to_gold` DAG (`airflow/dags/pipeline_dag.py`) running in Airflow: three task groups — `sales`, `marketing`, `cross_domain` — each executing as its own Kubernetes pod via Astronomer Cosmos, `cross_domain` gated behind the other two finishing.

## Concepts covered
- **Astronomer Cosmos**: turns a dbt project into Airflow tasks. We use its `kubernetes` execution mode — each Cosmos-generated task is a `KubernetesPodOperator` under the hood, so a task group is really "one pod, running one `dbt build --select ...` call, per domain"
- **`LoadMode.DBT_MANIFEST`**: how Cosmos figures out what tasks to create, without running `dbt` live against BigQuery at DAG-parse time. See the module docstring in `pipeline_dag.py` — this is a direct consequence of Exercise 01's IAM split, not an arbitrary choice
- **Two different `dbt_project_path`s in one config**: `render_config`'s path is where the *scheduler* looks (the gitSync'd local copy) to parse the DAG; `execution_config`'s path is where the *pod* looks (`/dbt`, baked into the image by `dbt/Dockerfile`) to actually run `dbt build`. Same project, two different filesystems, at two different times
- `[a, b] >> c`: Airflow's dependency operator — `cross_domain_group` only starts once both `sales_group` and `marketing_group` have fully succeeded

## Why this matters
This is where the three biggest decisions from the grilling session become real code at once: domain-grouped pods (ADR 0003) instead of one pod per model or one pod for everything; manifest-based parsing forced by the IAM split from Exercise 01; and `cross_domain` as a genuinely separate task group because `customer_360` can't belong to either domain. If any one of these were done differently, this DAG would need to look different — this file is the concrete artifact of every trade-off discussed so far.

## Prerequisites
- Exercises 02-04 complete (Airflow running, bronze seeded, dbt project builds cleanly)
- `pip install astronomer-cosmos` locally (for building the manifest — Cosmos itself doesn't need to run outside Airflow, but `dbt parse` does)
- Artifact Registry enabled: `gcloud services enable artifactregistry.googleapis.com`

## Steps

### 1. Create an Artifact Registry repo and build the dbt runner image
```bash
gcloud artifacts repositories create data-pipeline \
  --repository-format=docker --location=europe-west1 --project "$GCP_PROJECT_ID"
gcloud auth configure-docker europe-west1-docker.pkg.dev

IMAGE="europe-west1-docker.pkg.dev/${GCP_PROJECT_ID}/data-pipeline/dbt-runner:latest"
docker build -t "$IMAGE" dbt/
docker push "$IMAGE"
```
This is the image `common_operator_args["image"]` in `pipeline_dag.py` references via the `DBT_IMAGE` env var — it's what actually runs on the pods Cosmos launches.

### 2. Generate the manifest the scheduler will parse
```bash
cd dbt/pipeline
export DBT_PROFILES_DIR=.
dbt parse
cd ../..
```
`dbt parse` resolves every model, source, and ref into `target/manifest.json` without executing any SQL or connecting to BigQuery — which is exactly why the scheduler can use it despite `airflow-runner` having no BigQuery grants. Commit it:
```bash
git add dbt/pipeline/target/manifest.json
git commit -m "Add compiled dbt manifest for Airflow DAG parsing"
git push
```
In a real pipeline this step runs in CI whenever a model changes, not by hand — noted here as a known gap, not solved by this course (see the EL-step trade-off in `docs/adr/0002-preseeded-bronze-fixtures.md` for the same kind of scoping call).

### 3. Set the image reference and push the DAG
```bash
export DBT_IMAGE="$IMAGE"
git add airflow/dags/pipeline_dag.py
git commit -m "Add bronze_to_gold DAG"
git push
```
gitSync (Exercise 02) picks this up within its polling interval — no `helm upgrade` needed to ship a DAG change.

### 4. Confirm the DAG parsed and unpause it
```bash
kubectl port-forward -n data-pipeline svc/airflow-webserver 8080:8080 &
```
In the UI: `bronze_to_gold` should appear in the DAGs list within a minute or two. Toggle it on (unpause), then trigger a manual run with the play button.

### 5. Watch the pods Cosmos launches
```bash
kubectl get pods -n data-pipeline -w
```
You should see three pods appear in sequence: `sales` and `marketing` first (they can run concurrently — nothing in the DAG orders them relative to each other), then `cross-domain` only after both exit `Completed`.

## Verify
**In the Console:** [Kubernetes Engine → Workloads](https://console.cloud.google.com/kubernetes/workload) filtered to `data-pipeline` shows the three task pods appear and disappear over the run (`is_delete_operator_pod: True` in `common_operator_args` cleans them up on success). The Airflow UI's Graph view for `bronze_to_gold` shows the same three-group shape as the DAG file: `sales` and `marketing` side by side, both feeding into `cross_domain`.

**On the CLI:**
```bash
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM \`${GCP_PROJECT_ID}.gke_gold.customer_360\`"
```
A non-zero count run through the DAG (not `dbt build` from your machine, as in Exercise 04) confirms the whole chain — gitSync, manifest parsing, pod scheduling, Workload Identity — actually worked end to end.

## Stretch goal
Delete the `dbt-runner` KSA's `iam.gke.io/gcp-service-account` annotation (`kubectl annotate serviceaccount dbt-runner -n data-pipeline iam.gke.io/gcp-service-account- `), trigger the DAG again, and watch the `sales` pod's logs. It fails on a BigQuery auth error, not a Kubernetes scheduling error — the pod itself starts fine, because Workload Identity is invisible to Kubernetes scheduling; it only affects what the process *inside* the pod can authenticate as. Re-annotate to fix it.
