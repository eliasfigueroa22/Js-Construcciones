-- Budget vs actual spend analysis per obra x rubro
-- Uses presupuesto_cliente for budgeted amounts and actual spend from compras + pagos
with presupuesto as (
    select
        obra_id,
        rubro_id,
        sum(monto_total) as monto_presupuestado
    from {{ ref('stg_fact_presupuesto_cliente') }}
    where estado = 'APROBADO' or estado is null
    group by obra_id, rubro_id
),

gasto_materiales as (
    select
        obra_id,
        rubro_id,
        rubro_nombre,
        sum(monto_total) as monto_materiales
    from {{ ref('int_compras_enriched') }}
    group by obra_id, rubro_id, rubro_nombre
),

gasto_mano_obra as (
    select
        obra_id,
        rubro_id,
        sum(monto_pago) as monto_mano_obra
    from {{ ref('int_pagos_enriched') }}
    group by obra_id, rubro_id
),

combinado as (
    select
        coalesce(m.obra_id, p2.obra_id) as obra_id,
        coalesce(m.rubro_id, p2.rubro_id) as rubro_id,
        m.rubro_nombre,
        coalesce(m.monto_materiales, 0) + coalesce(p2.monto_mano_obra, 0) as monto_total_real
    from gasto_materiales m
    full outer join gasto_mano_obra p2
        on m.obra_id = p2.obra_id and m.rubro_id = p2.rubro_id
)

select
    c.obra_id,
    c.rubro_id,
    c.rubro_nombre,
    coalesce(p.monto_presupuestado, 0) as monto_presupuestado,
    c.monto_total_real,
    c.monto_total_real - coalesce(p.monto_presupuestado, 0) as desviacion,
    case
        when coalesce(p.monto_presupuestado, 0) > 0
        then round((c.monto_total_real - p.monto_presupuestado) / p.monto_presupuestado * 100, 2)
        else null
    end as pct_desviacion,
    case
        when coalesce(p.monto_presupuestado, 0) = 0 then 'SIN PRESUPUESTO'
        when c.monto_total_real <= p.monto_presupuestado then 'DENTRO DE PRESUPUESTO'
        when c.monto_total_real <= p.monto_presupuestado * 1.1 then 'LEVE DESVIO (+10%)'
        else 'DESVIO SIGNIFICATIVO (>10%)'
    end as clasificacion
from combinado c
left join presupuesto p on c.obra_id = p.obra_id and c.rubro_id = p.rubro_id
order by c.obra_id, c.monto_total_real desc
