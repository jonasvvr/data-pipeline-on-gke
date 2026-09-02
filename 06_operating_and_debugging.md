# Exercise 06: Operating & Debugging the Pipeline

## What you'll build
Nothing new — this exercise breaks the pipeline on purpose, twice, and uses what domain-grouped orchestration actually buys you (and what it doesn't) to find and fix each failure.

## Concepts covered
- Reading `KubernetesPodOperator` logs through the Airflow UI vs. `kubectl logs` directly — same data, two paths, the second one still works after `is_delete_operator_pod: True` deletes the pod (Airflow captured the logs before deletion; a raw `kubectl logs` on a pod that's already gone won't)
- Clearing a single failed task (Airflow UI: click the task instance → **Clear**) vs. re-triggering the whole DAG run — and what "single task" actually means here, given the granularity chosen in `docs/adr/0003-domain-grouped-orchestration.md`
- The specific failure mode Workload Identity produces when misconfigured (pod schedules and starts fine; the *process inside it* fails to authenticate) vs. a resource/scheduling failure (pod never leaves `Pending`)

## Why this matters
Exercise 05 built the happy path. Every real pipeline spends most of its life not on the happy path — a bad join breaks one model, a permissions change breaks a whole domain, a typo in a selector silently builds nothing. The debugging loop you build here is the actual day-to-day skill; getting the DAG to run once is not.

## Prerequisites
- Exercise 05 complete, `bronze_to_gold` has run successfully at least once

## Steps

### 1. Break a single model, on purpose
Edit `dbt/pipeline/models/marts/sales/sales_summary.sql` and introduce a typo — change `order_amount` to `order_amont` on the `sum(...)` line. Regenerate the manifest, commit, and push:
```bash
cd dbt/pipeline && dbt parse && cd ../..
git add dbt/pipeline/models/marts/sales/sales_summary.sql dbt/pipeline/target/manifest.json
git commit -m "Break sales_summary on purpose"
git push
```

### 2. Trigger a run and find the failure
In the Airflow UI, trigger `bronze_to_gold`. The `sales` task group turns red. Click into it, open the task's **Logs** tab — the actual `dbt` compilation error (`column "order_amont" does not exist` or similar) is in there, printed by the pod before it exited non-zero.

### 3. Fix it and clear just the failed task
```bash
# revert the typo
cd dbt/pipeline && dbt parse && cd ../..
git add dbt/pipeline/models/marts/sales/sales_summary.sql dbt/pipeline/target/manifest.json
git commit -m "Fix sales_summary typo"
git push
```
In the UI: click the failed `sales` task group → **Clear** (not "trigger new DAG run"). This re-runs only that task group's pod — but notice it rebuilds *all* of `sales`'s staging + intermediate + marts models, not just `sales_summary`. That's the trade-off named in `docs/adr/0003-domain-grouped-orchestration.md`: domain-level retry granularity, not model-level. `marketing`, already succeeded, is untouched, and `cross_domain` waits for this retry the same way it waited the first time.

### 4. Break the identity binding instead
```bash
kubectl annotate serviceaccount dbt-runner -n data-pipeline iam.gke.io/gcp-service-account- 
```
Trigger the DAG again. This time watch `kubectl get pods -n data-pipeline -w` instead of the UI: the `sales` pod reaches `Running`, then exits non-zero shortly after — it was scheduled without any problem, because Kubernetes has no concept of Workload Identity; only the `google-auth` library inside the running process checks it, and fails when it can't find valid credentials. Compare this to a pod stuck in `Pending` (a resource/scheduling problem) — same red task in the UI, completely different root cause, and the log tab (not `kubectl describe pod`) is where you'd see this one.

### 5. Restore the binding
```bash
gcloud iam service-accounts add-iam-policy-binding "dbt-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:${GCP_PROJECT_ID}.svc.id.goog[data-pipeline/dbt-runner]"
kubectl annotate serviceaccount dbt-runner -n data-pipeline \
  "iam.gke.io/gcp-service-account=dbt-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
```
Clear the failed task group once more; it should now go green.

## Verify
**In the Console:** [Kubernetes Engine → Workloads → Logs](https://console.cloud.google.com/kubernetes/workload) (or [Logs Explorer](https://console.cloud.google.com/logs/query) filtered to `resource.type="k8s_container" AND resource.labels.namespace_name="data-pipeline"`) shows both failure runs' pod logs retained after the pods themselves were deleted — Cloud Logging captured stdout/stderr independently of pod lifecycle, which is why `is_delete_operator_pod: True` doesn't lose you anything.

**On the CLI:**
```bash
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${GCP_PROJECT_ID}.gke_gold.sales_summary\` LIMIT 5"
```
Confirms the final, fixed run actually landed correct data, not just a green checkmark in the UI.

## Stretch goal
Set `sales_group`'s `operator_args` to include `"retries": 2, "retry_delay": timedelta(minutes=1)` (per-task-group, not DAG-wide) and re-break the typo. Watch Airflow retry the `sales` pod twice before giving up — and notice retries don't help here, because the failure is deterministic (a syntax error fails identically every time). Retries are for transient failures (a flaky BigQuery API call, a pod preempted mid-run); knowing which category a given red task falls into, before blindly clicking retry, is most of what "operating a pipeline" actually is.
