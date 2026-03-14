with gastos as (
    select * from {{ ref('int_obra_gastos_totales') }}
),

totales as (
    select sum(total_gastos) as gran_total from gastos
)

select
    g.obra_id,
    g.nombre_obra,
    g.cliente_id,
    g.estado_obra,
    g.monto_contrato,
    g.total_materiales,
    g.total_mano_obra,
    g.total_gastos,
    g.total_ingresos,
    g.resultado_neto,
    round(g.total_gastos / nullif(t.gran_total, 0) * 100, 2) as pct_del_total,
    case
        when g.monto_contrato > 0
        then round(g.total_gastos / g.monto_contrato * 100, 2)
        else null
    end as pct_contrato_ejecutado,
    rank() over (order by g.total_gastos desc) as ranking_gasto
from gastos g
cross join totales t
order by g.total_gastos desc
