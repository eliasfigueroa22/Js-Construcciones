-- Ensures every compra references a valid obra via airtable_id
select
    c.compra_nro,
    c.obra_id
from {{ ref('stg_fact_compra') }} c
left join {{ ref('stg_dim_obras') }} o on c.obra_id = o.airtable_id
where c.obra_id is not null
  and o.airtable_id is null
