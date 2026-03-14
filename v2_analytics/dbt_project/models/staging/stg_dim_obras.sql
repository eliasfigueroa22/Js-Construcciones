with source as (
    select * from {{ source('raw', 'dim_obras') }}
),

renamed as (
    select
        cast("airtable_id" as varchar) as airtable_id,
        cast("ObraNro" as integer) as obra_nro,
        cast("NombreObra" as varchar) as nombre_obra,
        cast("ClienteID" as varchar) as cliente_id,
        trim(upper(cast("Clave" as varchar))) as clave,
        cast("FechaInicio" as date) as fecha_inicio,
        cast("FechaFinEstimada" as date) as fecha_fin_estimada,
        cast("FechaFinReal" as date) as fecha_fin_real,
        cast("Ubicacion_Ciudad" as varchar) as ubicacion_ciudad,
        cast("Ubicacion_Zona" as varchar) as ubicacion_zona,
        cast("Ubicacion_Direccion" as varchar) as ubicacion_direccion,
        trim(upper(cast("EstadoObra" as varchar))) as estado_obra,
        trim(upper(cast("CategoriaObra" as varchar))) as categoria_obra,
        {{ guaranies_format('"MontoContrato"') }} as monto_contrato,
        cast("Descripcion" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
