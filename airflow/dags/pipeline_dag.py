"""
Bronze -> silver -> gold pipeline, orchestrated domain-by-domain.

Each DbtTaskGroup below runs as its own Kubernetes pod (Cosmos execution_mode
KUBERNETES) built from the `data-pipeline-dbt` image (see ../../dbt/Dockerfile).
`sales` and `marketing` build their own staging/intermediate/marts models
independently and can run in parallel; `cross_domain` builds customer_360,
which joins across both, so it only starts once both finish.

See ../../docs/adr/0003-domain-grouped-orchestration.md for why the split is
by domain rather than by individual dbt model.

DAG *parsing* (the scheduler figuring out what tasks exist) is deliberately
manifest-based (LoadMode.DBT_MANIFEST), not live (dbt ls/dbt parse against
BigQuery): `airflow-runner`, the KSA the scheduler pod runs as, has zero
BigQuery grants (manifests/01-provision/serviceaccounts.yaml) -- only
`dbt-runner`, used by the per-domain pods below at task *runtime*, can query
BigQuery at all. Manifest-based loading needs nothing more than the
target/manifest.json file gitSync already pulled in alongside this DAG.
"""

import os
from datetime import datetime
from pathlib import Path

from cosmos import DbtTaskGroup, ExecutionConfig, ExecutionMode, LoadMode, ProfileConfig, ProjectConfig, RenderConfig
from airflow import DAG

DBT_IMAGE = os.getenv("DBT_IMAGE", "data-pipeline-dbt:latest")
K8S_NAMESPACE = os.getenv("PIPELINE_NAMESPACE", "data-pipeline")
K8S_SERVICE_ACCOUNT = os.getenv("PIPELINE_KSA", "dbt-runner")

# Parse-time: the local, gitSync'd copy the scheduler reads to render the DAG.
SYNCED_DBT_DIR = Path(__file__).resolve().parent.parent / "dbt" / "pipeline"
# Runtime: the path *inside* the dbt-runner pod (baked in by ../../dbt/Dockerfile).
POD_DBT_DIR = "/dbt"

profile_config = ProfileConfig(
    profile_name="pipeline",
    target_name="gke",
    profiles_yml_filepath=SYNCED_DBT_DIR / "profiles.yml",
)

def render_config_for(select: list[str]) -> RenderConfig:
    return RenderConfig(load_method=LoadMode.DBT_MANIFEST, select=select)


execution_config = ExecutionConfig(
    execution_mode=ExecutionMode.KUBERNETES,
    dbt_project_path=POD_DBT_DIR,
)

common_operator_args = {
    "image": DBT_IMAGE,
    "namespace": K8S_NAMESPACE,
    "service_account_name": K8S_SERVICE_ACCOUNT,  # Workload Identity -> GCP SA with BigQuery access
    "get_logs": True,
    "is_delete_operator_pod": True,
    "env_vars": {"GCP_PROJECT_ID": os.environ["GCP_PROJECT_ID"]},
}

with DAG(
    dag_id="bronze_to_gold",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["dbt", "bigquery", "medallion"],
) as dag:

    project_config = ProjectConfig(
        dbt_project_path=SYNCED_DBT_DIR,
        manifest_path=SYNCED_DBT_DIR / "target" / "manifest.json",
    )

    sales_group = DbtTaskGroup(
        group_id="sales",
        project_config=project_config,
        profile_config=profile_config,
        execution_config=execution_config,
        render_config=render_config_for(
            [
                "path:models/staging/sales",
                "path:models/intermediate/sales",
                "path:models/marts/sales",
            ]
        ),
        operator_args=common_operator_args,
    )

    marketing_group = DbtTaskGroup(
        group_id="marketing",
        project_config=project_config,
        profile_config=profile_config,
        execution_config=execution_config,
        render_config=render_config_for(
            [
                "path:models/staging/marketing",
                "path:models/intermediate/marketing",
                "path:models/marts/marketing",
            ]
        ),
        operator_args=common_operator_args,
    )

    cross_domain_group = DbtTaskGroup(
        group_id="cross_domain",
        project_config=project_config,
        profile_config=profile_config,
        execution_config=execution_config,
        render_config=render_config_for(["path:models/marts/cross_domain"]),
        operator_args=common_operator_args,
    )

    [sales_group, marketing_group] >> cross_domain_group
