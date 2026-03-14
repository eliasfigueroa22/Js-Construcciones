with source as (
    select * from {{ source('raw', 'fact_ingreso') }}
),

renamed as (
    select
        cast("IngresoNro" as integer) as ingreso_nro,
        cast("ObraID" as varchar) as obra_id,
        cast("FechaIngreso" as date) as fecha_ingreso,
        cast("FechaFactura" as date) as fecha_factura,
        cast("NumeroFactura" as varchar) as numero_factura,
        cast("TipoIngreso" as varchar) as tipo_ingreso,
        cast("Concepto" as varchar) as concepto,
        {{ guaranies_format('"MontoFacturado"') }} as monto_facturado,
        {{ guaranies_format('"MontoRecibido"') }} as monto_recibido,
        trim(upper(cast("EstadoCobro" as varchar))) as estado_cobro,
        cast("FechaCobro" as date) as fecha_cobro,
        cast("MetodoPago" as varchar) as metodo_pago,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
