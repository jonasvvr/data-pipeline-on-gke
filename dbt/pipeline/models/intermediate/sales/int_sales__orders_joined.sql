with orders as (
    select * from {{ ref('stg_sales__orders') }}
),

customers as (
    select * from {{ ref('stg_sales__customers') }}
)

select
    orders.order_id,
    orders.order_date,
    orders.order_amount,
    orders.order_status,
    customers.customer_id,
    customers.email,
    customers.customer_country
from orders
left join customers on orders.customer_id = customers.customer_id
