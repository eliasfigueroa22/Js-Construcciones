with source as (
    select * from {{ source('raw', 'dim_rubro') }}
),

renamed as (
    select
        cast("airtable_id" as varchar) as airtable_id,
        cast("RubroNro" as integer) as rubro_nro,
        trim(upper(cast("Rubro" as varchar))) as rubro,
        cast("NombreCompleto" as varchar) as nombre_completo,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
