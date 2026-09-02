with source as (
    select * from {{ source('marketing', 'raw_leads') }}
)

select
    lead_id,
    email,
    campaign_id,
    created_date as lead_created_date,
    converted_customer_id
from source
