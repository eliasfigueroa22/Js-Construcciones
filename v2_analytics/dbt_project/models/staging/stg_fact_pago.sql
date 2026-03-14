with source as (
    select * from {{ source('raw', 'fact_pago') }}
),

renamed as (
    select
        cast("PagoNro" as integer) as pago_nro,
        cast("ObraID" as varchar) as obra_id,
        cast("SectorID" as varchar) as sector_id,
        cast("TrabajadorID" as varchar) as trabajador_id,
        cast("RubroID" as varchar) as rubro_id,
        cast("PresupuestoSubcontratistaID" as varchar) as presupuesto_subcontratista_id,
        cast("FechaPago" as date) as fecha_pago,
        cast("Concepto" as varchar) as concepto,
        trim(upper(cast("TipoPago" as varchar))) as tipo_pago,
        {{ guaranies_format('"MontoPago"') }} as monto_pago,
        trim(upper(cast("MetodoPago" as varchar))) as metodo_pago,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
