with source as (
    select * from {{ source('raw', 'dim_trabajador') }}
),

renamed as (
    select
        cast("airtable_id" as varchar) as airtable_id,
        cast("TrabajadorNro" as integer) as trabajador_nro,
        trim(upper(cast("NombreCompleto" as varchar))) as nombre_completo,
        trim(upper(cast("TipoPersonal" as varchar))) as tipo_personal,
        cast("RUC_CI" as varchar) as ruc_ci,
        cast("Telefono" as varchar) as telefono,
        cast("RubroID" as varchar) as rubro_id,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
