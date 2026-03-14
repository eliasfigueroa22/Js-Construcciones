{{ config(severity='warn') }}
-- Ensures no negative amounts exist in key financial columns
with negative_amounts as (
    select 'fact_compra' as tabla, compra_nro as id, monto_total as monto
    from {{ ref('stg_fact_compra') }}
    where monto_total is not null and monto_total < 0

    union all

    select 'fact_pago', pago_nro, monto_pago
    from {{ ref('stg_fact_pago') }}
    where monto_pago is not null and monto_pago < 0

    union all

    select 'fact_ingreso', ingreso_nro, monto_recibido
    from {{ ref('stg_fact_ingreso') }}
    where monto_recibido is not null and monto_recibido < 0

    union all

    select 'fact_deuda', deuda_nro, monto_deuda
    from {{ ref('stg_fact_deuda') }}
    where monto_deuda is not null and monto_deuda < 0
)

select * from negative_amounts
