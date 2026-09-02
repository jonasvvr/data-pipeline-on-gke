{#
    dbt's default behavior suffixes the target dataset with the custom schema
    (target "pipeline" + custom schema "gke_bronze" -> "pipeline_gke_bronze").
    We want gke_bronze/gke_silver/gke_gold as their own top-level BigQuery
    datasets instead, so a model's `+schema:` config (set per-layer in
    dbt_project.yml) is used as-is.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
