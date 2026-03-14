with source as (
    select * from {{ source('raw', 'fact_pago_deuda') }}
),

renamed as (
    select
        cast("PagoDeudaNro" as integer) as pago_deuda_nro,
        cast("DeudaID" as varchar) as deuda_id,
        cast("FechaPago" as date) as fecha_pago,
        {{ guaranies_format('"MontoPagado"') }} as monto_pagado,
        trim(upper(cast("MetodoPago" as varchar))) as metodo_pago,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
