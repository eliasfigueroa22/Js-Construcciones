with source as (
    select * from {{ source('raw', 'fact_presupuesto_subcontratista') }}
),

renamed as (
    select
        airtable_id,
        cast("PresupuestoSubcontratistaNro" as integer) as presupuesto_subcontratista_nro,
        cast("TrabajadorID" as varchar) as trabajador_id,
        cast("ObraID" as varchar) as obra_id,
        cast("SectorID" as varchar) as sector_id,
        cast("RubroID" as varchar) as rubro_id,
        cast("FechaPresupuesto" as date) as fecha_presupuesto,
        cast("Concepto/Descripcion" as varchar) as concepto,
        {{ guaranies_format('"MontoPresupuestado"') }} as monto_presupuestado,
        {{ clean_percentage('"PorcentajeFacturacion"') }} as porcentaje_facturacion,
        trim(upper(cast("Estado" as varchar))) as estado,
        cast("Observaciones" as varchar) as observaciones,
        cast("_extracted_at" as timestamp) as _extracted_at
    from source
)

select * from renamed
