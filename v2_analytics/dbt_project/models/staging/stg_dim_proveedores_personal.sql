with source as (
    select * from {{ source('raw', 'dim_proveedores_personal') }}
),

renamed as (
    select
        cast("airtable_id" as varchar) as airtable_id,
        cast("ProveedorPersonalNro" as integer) as proveedor_personal_nro,
        trim(upper(cast("NombreProveedor" as varchar))) as nombre_proveedor,
        cast("RUC" as varchar) as ruc,
        cast("Telefono" as varchar) as telefono,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
