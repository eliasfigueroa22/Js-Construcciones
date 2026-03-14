with presupuestos as (
    select * from {{ ref('stg_fact_presupuesto_subcontratista') }}
),

facturacion as (
    select
        presupuesto_subcontratista_id,
        sum(monto_facturado) as total_facturado,
        count(*) as qty_facturas
    from {{ ref('stg_fact_facturacion_subcontratista') }}
    group by presupuesto_subcontratista_id
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
),

obras as (
    select airtable_id, clave, nombre_obra
    from {{ ref('stg_dim_obras') }}
)

select
    ps.presupuesto_subcontratista_nro,
    t.nombre_completo as trabajador_id,
    t.tipo_personal,
    o.clave as obra_id,
    o.nombre_obra,
    r.rubro as rubro_id,
    r.rubro_nombre,
    s.nombre_sector as sector,
    ps.concepto,
    ps.fecha_presupuesto,
    ps.monto_presupuestado,
    ps.porcentaje_facturacion,
    ps.estado,
    coalesce(f.total_facturado, 0) as total_facturado,
    coalesce(f.qty_facturas, 0) as qty_facturas,
    ps.monto_presupuestado - coalesce(f.total_facturado, 0) as saldo_pendiente,
    case
        when ps.monto_presupuestado > 0
        then round(coalesce(f.total_facturado, 0) / ps.monto_presupuestado * 100, 2)
        else 0
    end as porcentaje_ejecutado
from presupuestos ps
left join facturacion f on ps.airtable_id = f.presupuesto_subcontratista_id
left join trabajadores t on ps.trabajador_id = t.airtable_id
left join obras o on ps.obra_id = o.airtable_id
left join rubros r on ps.rubro_id = r.airtable_id
left join sectores s on ps.sector_id = s.airtable_id
