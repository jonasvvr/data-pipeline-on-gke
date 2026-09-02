with source as (
    select * from {{ source('sales', 'raw_orders') }}
)

select
    order_id,
    customer_id,
    order_date,
    amount as order_amount,
    status as order_status
from source
