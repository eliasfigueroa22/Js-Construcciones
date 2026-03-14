with compras_mes as (
    select
        date_trunc('month', fecha_compra) as mes,
        'MATERIALES' as tipo_gasto,
        sum(monto_total) as monto
    from {{ ref('stg_fact_compra') }}
    group by date_trunc('month', fecha_compra)
),

pagos_mes as (
    select
        date_trunc('month', fecha_pago) as mes,
        'MANO DE OBRA' as tipo_gasto,
        sum(monto_pago) as monto
    from {{ ref('stg_fact_pago') }}
    group by date_trunc('month', fecha_pago)
),

ingresos_mes as (
    select
        date_trunc('month', fecha_ingreso) as mes,
        'INGRESOS' as tipo_gasto,
        sum(monto_recibido) as monto
    from {{ ref('stg_fact_ingreso') }}
    group by date_trunc('month', fecha_ingreso)
),

all_monthly as (
    select * from compras_mes
    union all
    select * from pagos_mes
    union all
    select * from ingresos_mes
)

select
    mes,
    tipo_gasto,
    monto,
    lag(monto) over (partition by tipo_gasto order by mes) as monto_mes_anterior,
    case
        when lag(monto) over (partition by tipo_gasto order by mes) > 0
        then round(
            (monto - lag(monto) over (partition by tipo_gasto order by mes))
            / lag(monto) over (partition by tipo_gasto order by mes) * 100, 2
        )
        else null
    end as variacion_pct,
    sum(monto) over (partition by tipo_gasto order by mes) as acumulado_ytd
from all_monthly
order by mes, tipo_gasto
