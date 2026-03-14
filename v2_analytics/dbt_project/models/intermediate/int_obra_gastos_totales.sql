with materiales as (
    select
        obra_id,
        sum(monto_total) as total_materiales,
        count(*) as qty_compras
    from {{ ref('stg_fact_compra') }}
    group by obra_id
),

mano_obra as (
    select
        obra_id,
        sum(monto_pago) as total_mano_obra,
        count(*) as qty_pagos
    from {{ ref('stg_fact_pago') }}
    group by obra_id
),

ingresos as (
    select
        obra_id,
        sum(monto_recibido) as total_ingresos,
        count(*) as qty_ingresos
    from {{ ref('stg_fact_ingreso') }}
    group by obra_id
),

obras as (
    select
        airtable_id,
        clave,
        nombre_obra,
        cliente_id,
        estado_obra,
        monto_contrato
    from {{ ref('stg_dim_obras') }}
)

select
    o.clave as obra_id,
    o.nombre_obra,
    o.cliente_id,
    o.estado_obra,
    o.monto_contrato,
    coalesce(m.total_materiales, 0) as total_materiales,
    coalesce(m.qty_compras, 0) as qty_compras,
    coalesce(mo.total_mano_obra, 0) as total_mano_obra,
    coalesce(mo.qty_pagos, 0) as qty_pagos,
    coalesce(m.total_materiales, 0) + coalesce(mo.total_mano_obra, 0) as total_gastos,
    coalesce(i.total_ingresos, 0) as total_ingresos,
    coalesce(i.qty_ingresos, 0) as qty_ingresos,
    coalesce(i.total_ingresos, 0) - (coalesce(m.total_materiales, 0) + coalesce(mo.total_mano_obra, 0)) as resultado_neto
from obras o
left join materiales m on o.airtable_id = m.obra_id
left join mano_obra mo on o.airtable_id = mo.obra_id
left join ingresos i on o.airtable_id = i.obra_id
