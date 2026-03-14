with obras as (
    select * from {{ ref('stg_dim_obras') }}
),

gastos as (
    select * from {{ ref('int_obra_gastos_totales') }}
),

sectores as (
    select
        obra_id,
        count(*) as qty_sectores
    from {{ ref('stg_dim_sector') }}
    group by obra_id
),

trabajadores as (
    select
        obra_id,
        count(distinct trabajador_id) as qty_trabajadores
    from {{ ref('stg_fact_pago') }}
    group by obra_id
),

proveedores as (
    select
        obra_id,
        count(distinct proveedor_id) as qty_proveedores
    from {{ ref('stg_fact_compra') }}
    group by obra_id
)

select
    o.obra_nro,
    o.clave as obra_id,
    o.nombre_obra,
    o.estado_obra,
    o.categoria_obra,
    o.monto_contrato,
    o.fecha_inicio,
    o.fecha_fin_estimada,
    o.fecha_fin_real,
    o.ubicacion_ciudad,
    o.ubicacion_zona,
    o.ubicacion_direccion,
    coalesce(g.total_materiales, 0) as total_materiales,
    coalesce(g.total_mano_obra, 0) as total_mano_obra,
    coalesce(g.total_gastos, 0) as total_gastos,
    coalesce(g.total_ingresos, 0) as total_ingresos,
    coalesce(g.resultado_neto, 0) as resultado_neto,
    coalesce(g.qty_compras, 0) as qty_compras,
    coalesce(g.qty_pagos, 0) as qty_pagos,
    coalesce(s.qty_sectores, 0) as qty_sectores,
    coalesce(t.qty_trabajadores, 0) as qty_trabajadores,
    coalesce(p.qty_proveedores, 0) as qty_proveedores,
    case
        when o.monto_contrato > 0
        then round(coalesce(g.total_gastos, 0) / o.monto_contrato * 100, 2)
        else null
    end as pct_contrato_ejecutado
from obras o
left join gastos g on o.clave = g.obra_id
left join sectores s on o.airtable_id = s.obra_id
left join trabajadores t on o.airtable_id = t.obra_id
left join proveedores p on o.airtable_id = p.obra_id
