with source as (
    select * from {{ source('raw', 'fact_presupuesto_cliente') }}
),

renamed as (
    select
        cast("PresupuestoClienteNro" as integer) as presupuesto_cliente_nro,
        cast("ObraID" as varchar) as obra_id,
        cast("SectorID" as varchar) as sector_id,
        cast("RubroID" as varchar) as rubro_id,
        cast("TipoPresupuesto" as varchar) as tipo_presupuesto,
        cast("NumeroVersion" as varchar) as numero_version,
        cast("FechaPresupuesto" as date) as fecha_presupuesto,
        cast("FechaAprobacion" as date) as fecha_aprobacion,
        cast("Descripcion" as varchar) as descripcion,
        cast("Cantidad" as decimal(18,4)) as cantidad,
        cast("Unidad" as varchar) as unidad,
        {{ guaranies_format('"PrecioUnitario"') }} as precio_unitario,
        {{ guaranies_format('"MontoTotal"') }} as monto_total,
        trim(upper(cast("Estado" as varchar))) as estado,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
