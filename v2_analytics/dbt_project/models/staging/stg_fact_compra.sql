with source as (
    select * from {{ source('raw', 'fact_compra') }}
),

renamed as (
    select
        cast("CompraNro" as integer) as compra_nro,
        cast("ObraID" as varchar) as obra_id,
        cast("SectorID" as varchar) as sector_id,
        cast("ProveedorID" as varchar) as proveedor_id,
        cast("RubroID" as varchar) as rubro_id,
        cast("FechaCompra" as date) as fecha_compra,
        cast("NumeroDocumento" as varchar) as numero_documento,
        trim(upper(cast("TipoDocumento" as varchar))) as tipo_documento,
        cast("Descripcion" as varchar) as descripcion,
        cast("Cantidad" as decimal(18,4)) as cantidad,
        cast("Unidad" as varchar) as unidad,
        {{ guaranies_format('"MontoTotal"') }} as monto_total,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
