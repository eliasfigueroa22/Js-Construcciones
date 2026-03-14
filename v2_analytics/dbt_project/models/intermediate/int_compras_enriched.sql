with compras as (
    select * from {{ ref('stg_fact_compra') }}
),

obras as (
    select airtable_id, clave, nombre_obra, cliente_id, estado_obra
    from {{ ref('stg_dim_obras') }}
),

proveedores as (
    select airtable_id, nombre_proveedor
    from {{ ref('stg_dim_proveedores') }}
),

rubros as (
    select airtable_id, rubro, nombre_completo as rubro_nombre
    from {{ ref('stg_dim_rubro') }}
),

sectores as (
    select airtable_id, nombre_sector, obra_id as sector_obra_id
    from {{ ref('stg_dim_sector') }}
)

select
    c.compra_nro,
    c.fecha_compra,
    o.clave as obra_id,
    o.nombre_obra,
    o.estado_obra,
    s.nombre_sector as sector,
    p.nombre_proveedor as proveedor_id,
    r.rubro as rubro_id,
    r.rubro_nombre,
    c.tipo_documento,
    c.numero_documento,
    c.descripcion,
    c.cantidad,
    c.unidad,
    c.monto_total,
    c.observaciones
from compras c
left join obras o on c.obra_id = o.airtable_id
left join proveedores p on c.proveedor_id = p.airtable_id
left join rubros r on c.rubro_id = r.airtable_id
left join sectores s on c.sector_id = s.airtable_id
