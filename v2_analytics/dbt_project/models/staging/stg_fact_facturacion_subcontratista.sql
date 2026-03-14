with source as (
    select * from {{ source('raw', 'fact_facturacion_subcontratista') }}
),

renamed as (
    select
        cast("FacturacionNro" as integer) as facturacion_nro,
        cast("PresupuestoSubcontratistaID" as varchar) as presupuesto_subcontratista_id,
        cast("FechaFactura" as date) as fecha_factura,
        cast("NumeroFactura" as varchar) as numero_factura,
        {{ guaranies_format('"MontoFacturado"') }} as monto_facturado,
        {{ clean_percentage('"PorcentajeAplicado"') }} as porcentaje_aplicado,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
