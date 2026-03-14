-- ============================================================================
-- Expense concentration by category (rubro) within each project
-- Demonstrates: PARTITION BY, RANK, percentage within groups, ROLLUP pattern
-- ============================================================================
WITH gasto_por_rubro AS (
    SELECT
        o.clave AS obra_id,
        o.nombre_obra,
        r.rubro AS rubro_codigo,
        r.nombre_completo AS rubro_nombre,
        SUM(c.monto_total) AS monto_materiales,
        COUNT(*) AS qty_compras
    FROM main_staging.stg_fact_compra c
    LEFT JOIN main_staging.stg_dim_obras o ON c.obra_id = o.airtable_id
    LEFT JOIN main_staging.stg_dim_rubro r ON c.rubro_id = r.airtable_id
    GROUP BY o.clave, o.nombre_obra, r.rubro, r.nombre_completo
),

con_metricas AS (
    SELECT
        obra_id,
        nombre_obra,
        rubro_codigo,
        rubro_nombre,
        monto_materiales,
        qty_compras,
        -- % of this rubro within the project
        ROUND(monto_materiales / SUM(monto_materiales) OVER (PARTITION BY obra_id) * 100, 2) AS pct_en_obra,
        -- Ranking within the project
        RANK() OVER (PARTITION BY obra_id ORDER BY monto_materiales DESC) AS ranking_en_obra,
        -- % of this rubro across all projects
        ROUND(monto_materiales / SUM(monto_materiales) OVER () * 100, 2) AS pct_global
    FROM gasto_por_rubro
)

SELECT
    obra_id,
    nombre_obra,
    rubro_codigo,
    rubro_nombre,
    monto_materiales,
    qty_compras,
    pct_en_obra,
    ranking_en_obra,
    pct_global,
    -- Cumulative % within each project (to find top rubros covering 80%)
    SUM(pct_en_obra) OVER (
        PARTITION BY obra_id ORDER BY monto_materiales DESC
    ) AS pct_acumulado_en_obra
FROM con_metricas
ORDER BY obra_id, ranking_en_obra;
