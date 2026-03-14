with source as (
    select * from {{ source('raw', 'fact_compras_personal') }}
),

renamed as (
    select
        cast("GastoPersonalNro" as integer) as gasto_personal_nro,
        cast("ProveedorID" as varchar) as proveedor_id,
        cast("FechaGasto" as date) as fecha_gasto,
        cast("Descripcion" as varchar) as descripcion,
        cast("Cantidad" as decimal(18,4)) as cantidad,
        cast("Unidad" as varchar) as unidad,
        {{ guaranies_format('"MontoGasto"') }} as monto_gasto,
        trim(upper(cast("TipoDocumento" as varchar))) as tipo_documento,
        cast("NumeroDocumento" as varchar) as numero_documento,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
