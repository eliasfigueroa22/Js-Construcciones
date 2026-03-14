with source as (
    select * from {{ source('raw', 'dim_clientes') }}
),

renamed as (
    select
        cast("airtable_id" as varchar) as airtable_id,
        cast("ClienteNro" as integer) as cliente_nro,
        trim(upper(cast("NombreCliente" as varchar))) as nombre_cliente,
        cast("RUC" as varchar) as ruc,
        cast("Direccion" as varchar) as direccion,
        cast("Telefono" as varchar) as telefono,
        cast("Email" as varchar) as email,
        trim(upper(cast("TipoCliente" as varchar))) as tipo_cliente,
        cast("FechaRegistro" as date) as fecha_registro,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
