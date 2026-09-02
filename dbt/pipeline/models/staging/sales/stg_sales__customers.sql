with source as (
    select * from {{ source('sales', 'raw_customers') }}
)

select
    customer_id,
    email,
    signup_date,
    country as customer_country
from source
