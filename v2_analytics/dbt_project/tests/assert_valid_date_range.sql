{{ config(severity='warn') }}
-- Ensures all dates fall within the valid business period (Jan 2024 – present)
with invalid_dates as (
    select 'fact_compra' as tabla, compra_nro as id, fecha_compra as fecha
    from {{ ref('stg_fact_compra') }}
    where fecha_compra is not null
      and (fecha_compra < '2024-01-01' or fecha_compra > current_date)

    union all

    select 'fact_pago', pago_nro, fecha_pago
    from {{ ref('stg_fact_pago') }}
    where fecha_pago is not null
      and (fecha_pago < '2024-01-01' or fecha_pago > current_date)

    union all

    select 'fact_ingreso', ingreso_nro, fecha_ingreso
    from {{ ref('stg_fact_ingreso') }}
    where fecha_ingreso is not null
      and (fecha_ingreso < '2024-01-01' or fecha_ingreso > current_date)
)

select * from invalid_dates
