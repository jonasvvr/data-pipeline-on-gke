-- Cross-domain mart: the one model where sales and marketing intentionally meet.
with sales as (
    select * from {{ ref('sales_summary') }}
),

leads as (
    select * from {{ ref('int_marketing__leads_joined') }}
    where converted_customer_id is not null
)

select
    sales.customer_id,
    sales.email,
    sales.customer_country,
    sales.completed_order_count,
    sales.lifetime_value,
    leads.campaign_id as acquisition_campaign_id,
    leads.campaign_name as acquisition_campaign_name,
    leads.campaign_channel as acquisition_channel
from sales
left join leads on sales.customer_id = leads.converted_customer_id
