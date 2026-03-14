with source as (
    select * from {{ source('raw', 'dim_sector') }}
),

renamed as (
    select
        cast("airtable_id" as varchar) as airtable_id,
        cast("SectorNro" as integer) as sector_nro,
        cast("ObraID" as varchar) as obra_id,
        cast("NombreSector" as varchar) as nombre_sector,
        cast("Descripcion" as varchar) as descripcion,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
