-- ============================================================================
-- Pareto Analysis: Top suppliers that represent 80% of total spend
-- Demonstrates: Window functions (SUM OVER), CASE, CTEs, cumulative %
-- ============================================================================
WITH proveedor_totals AS (
    SELECT
        p.nombre_proveedor,
        COUNT(*) AS qty_compras,
        COUNT(DISTINCT c.obra_id) AS qty_obras,
        SUM(c.monto_total) AS total_comprado
    FROM main_staging.stg_fact_compra c
    LEFT JOIN main_staging.stg_dim_proveedores p ON c.proveedor_id = p.airtable_id
    GROUP BY p.nombre_proveedor
),

ranked AS (
    SELECT
        nombre_proveedor,
        qty_compras,
        qty_obras,
        total_comprado,
        ROUND(total_comprado / SUM(total_comprado) OVER () * 100, 2) AS pct_del_total,
        ROUND(SUM(total_comprado) OVER (ORDER BY total_comprado DESC)
              / SUM(total_comprado) OVER () * 100, 2) AS pct_acumulado,
        ROW_NUMBER() OVER (ORDER BY total_comprado DESC) AS ranking
    FROM proveedor_totals
)

SELECT
    ranking,
    nombre_proveedor,
    qty_compras,
    qty_obras,
    total_comprado,
    pct_del_total,
    pct_acumulado,
    CASE
        WHEN pct_acumulado <= 80 THEN 'A (80%)'
        WHEN pct_acumulado <= 95 THEN 'B (15%)'
        ELSE 'C (5%)'
    END AS clasificacion_pareto
FROM ranked
ORDER BY ranking;
