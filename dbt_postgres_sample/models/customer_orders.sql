with customers as (
  select * from {{ ref('customers') }}
), orders as (
  select * from {{ ref('orders') }}
)
select
  c.customer_id,
  c.name,
  count(o.order_id) as orders_count,
  sum(o.amount) as total_amount
from customers c
join orders o on c.customer_id = o.customer_id
group by c.customer_id, c.name
