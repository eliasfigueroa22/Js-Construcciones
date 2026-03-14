with source as (
    select * from {{ source('raw', 'fact_deuda') }}
),

renamed as (
    select
        cast("DeudaNro" as integer) as deuda_nro,
        cast("TrabajadorID" as varchar) as trabajador_id,
        cast("ObraID" as varchar) as obra_id,
        trim(upper(cast("TipoDeuda" as varchar))) as tipo_deuda,
        cast("FechaSolicitud" as date) as fecha_solicitud,
        {{ guaranies_format('"MontoDeuda"') }} as monto_deuda,
        trim(upper(cast("Estado" as varchar))) as estado,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
