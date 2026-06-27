select id, amount * 2 as doubled from {{ ref('stg_orders') }}
