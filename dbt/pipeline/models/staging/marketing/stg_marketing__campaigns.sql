with source as (
    select * from {{ source('marketing', 'raw_campaigns') }}
)

select
    campaign_id,
    name as campaign_name,
    channel as campaign_channel,
    start_date as campaign_start_date,
    budget as campaign_budget
from source
