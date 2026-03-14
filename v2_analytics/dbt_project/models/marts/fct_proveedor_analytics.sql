with compras as (
    select * from {{ ref('int_compras_enriched') }}
),

proveedor_stats as (
    select
        proveedor_id,
        count(*) as qty_compras,
        count(distinct obra_id) as qty_obras,
        sum(monto_total) as total_comprado,
        avg(monto_total) as promedio_compra,
        min(fecha_compra) as primera_compra,
        max(fecha_compra) as ultima_compra
    from compras
    group by proveedor_id
),

ranked as (
    select
        *,
        sum(total_comprado) over (order by total_comprado desc) as acumulado,
        sum(total_comprado) over () as gran_total
    from proveedor_stats
)

select
    proveedor_id,
    qty_compras,
    qty_obras,
    total_comprado,
    promedio_compra,
    primera_compra,
    ultima_compra,
    round(total_comprado / nullif(gran_total, 0) * 100, 2) as pct_del_total,
    round(acumulado / nullif(gran_total, 0) * 100, 2) as pct_acumulado,
    case
        when round(acumulado / nullif(gran_total, 0) * 100, 2) <= 80 then 'A (80%)'
        when round(acumulado / nullif(gran_total, 0) * 100, 2) <= 95 then 'B (15%)'
        else 'C (5%)'
    end as clasificacion_pareto,
    rank() over (order by total_comprado desc) as ranking
from ranked
order by total_comprado desc
