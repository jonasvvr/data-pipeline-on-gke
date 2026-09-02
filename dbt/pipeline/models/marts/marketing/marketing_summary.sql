with leads as (
    select * from {{ ref('int_marketing__leads_joined') }}
)

select
    campaign_id,
    campaign_name,
    campaign_channel,
    campaign_budget,
    count(lead_id) as lead_count,
    count(converted_customer_id) as converted_count
from leads
group by campaign_id, campaign_name, campaign_channel, campaign_budget
