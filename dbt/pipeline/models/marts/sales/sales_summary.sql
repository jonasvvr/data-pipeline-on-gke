with orders as (
    select * from {{ ref('int_sales__orders_joined') }}
)

select
    customer_id,
    email,
    customer_country,
    count(order_id) as completed_order_count,
    sum(case when order_status = 'completed' then order_amount else 0 end) as lifetime_value
from orders
group by customer_id, email, customer_country
