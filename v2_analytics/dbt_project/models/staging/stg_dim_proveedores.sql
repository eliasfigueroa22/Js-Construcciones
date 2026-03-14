with source as (
    select * from {{ source('raw', 'dim_proveedores') }}
),

renamed as (
    select
        cast("airtable_id" as varchar) as airtable_id,
        cast("ProveedorNro" as integer) as proveedor_nro,
        trim(upper(cast("NombreProveedor" as varchar))) as nombre_proveedor,
        cast("RUC" as varchar) as ruc,
        cast("Telefono" as varchar) as telefono,
        cast("Email" as varchar) as email,
        cast("FechaRegistro" as date) as fecha_registro,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
