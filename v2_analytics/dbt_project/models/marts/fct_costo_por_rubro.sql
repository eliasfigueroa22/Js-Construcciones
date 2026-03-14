with compras_rubro as (
    select
        obra_id,
        nombre_obra,
        rubro_id,
        rubro_nombre,
        sum(monto_total) as total_materiales,
        count(*) as qty_compras
    from {{ ref('int_compras_enriched') }}
    group by obra_id, nombre_obra, rubro_id, rubro_nombre
),

pagos_rubro as (
    select
        obra_id,
        rubro_id,
        sum(monto_pago) as total_mano_obra,
        count(*) as qty_pagos
    from {{ ref('int_pagos_enriched') }}
    group by obra_id, rubro_id
)

select
    coalesce(c.obra_id, p.obra_id) as obra_id,
    c.nombre_obra,
    coalesce(c.rubro_id, p.rubro_id) as rubro_id,
    c.rubro_nombre,
    coalesce(c.total_materiales, 0) as total_materiales,
    coalesce(c.qty_compras, 0) as qty_compras,
    coalesce(p.total_mano_obra, 0) as total_mano_obra,
    coalesce(p.qty_pagos, 0) as qty_pagos,
    coalesce(c.total_materiales, 0) + coalesce(p.total_mano_obra, 0) as total_rubro,
    rank() over (
        partition by coalesce(c.obra_id, p.obra_id)
        order by coalesce(c.total_materiales, 0) + coalesce(p.total_mano_obra, 0) desc
    ) as ranking_en_obra
from compras_rubro c
full outer join pagos_rubro p
    on c.obra_id = p.obra_id and c.rubro_id = p.rubro_id
order by obra_id, total_rubro desc
