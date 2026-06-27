select id, amount from {{ ref('raw_orders') }}
