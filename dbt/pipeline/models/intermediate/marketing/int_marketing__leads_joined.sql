with leads as (
    select * from {{ ref('stg_marketing__leads') }}
),

campaigns as (
    select * from {{ ref('stg_marketing__campaigns') }}
)

select
    leads.lead_id,
    leads.email,
    leads.lead_created_date,
    leads.converted_customer_id,
    campaigns.campaign_id,
    campaigns.campaign_name,
    campaigns.campaign_channel,
    campaigns.campaign_budget
from leads
left join campaigns on leads.campaign_id = campaigns.campaign_id
