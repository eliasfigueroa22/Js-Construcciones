with pagos as (
    select * from {{ ref('stg_fact_pago') }}
),

obras as (
    select airtable_id, clave, nombre_obra, cliente_id, estado_obra
    from {{ ref('stg_dim_obras') }}
),

trabajadores as (
    select airtable_id, nombre_completo, tipo_personal
    from {{ ref('stg_dim_trabajador') }}
),

rubros as (
    select airtable_id, rubro, nombre_completo as rubro_nombre
    from {{ ref('stg_dim_rubro') }}
),

sectores as (
    select airtable_id, nombre_sector
    from {{ ref('stg_dim_sector') }}
)

select
    p.pago_nro,
    p.fecha_pago,
    o.clave as obra_id,
    o.nombre_obra,
    o.cliente_id,
    o.estado_obra,
    s.nombre_sector as sector,
    t.nombre_completo as trabajador_id,
    t.tipo_personal,
    r.rubro as rubro_id,
    r.rubro_nombre,
    p.concepto,
    p.tipo_pago,
    p.monto_pago,
    p.metodo_pago
from pagos p
left join obras o on p.obra_id = o.airtable_id
left join trabajadores t on p.trabajador_id = t.airtable_id
left join rubros r on p.rubro_id = r.airtable_id
left join sectores s on p.sector_id = s.airtable_id
