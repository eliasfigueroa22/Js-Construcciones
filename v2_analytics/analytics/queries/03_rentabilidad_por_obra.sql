-- ============================================================================
-- Profitability analysis per project: income vs total spend
-- Demonstrates: Multiple CTEs, COALESCE, CASE, RANK, percentage calculations
-- ============================================================================
WITH gastos_obra AS (
    SELECT
        o.clave AS obra_id,
        o.nombre_obra,
        o.estado_obra,
        o.monto_contrato,
        COALESCE(SUM(c.monto_total), 0) AS total_materiales,
        0 AS total_mano_obra
    FROM main_staging.stg_dim_obras o
    LEFT JOIN main_staging.stg_fact_compra c ON o.airtable_id = c.obra_id
    GROUP BY o.clave, o.nombre_obra, o.estado_obra, o.monto_contrato
),

pagos_obra AS (
    SELECT
        o.clave AS obra_id,
        COALESCE(SUM(p.monto_pago), 0) AS total_mano_obra
    FROM main_staging.stg_dim_obras o
    LEFT JOIN main_staging.stg_fact_pago p ON o.airtable_id = p.obra_id
    GROUP BY o.clave
),

ingresos_obra AS (
    SELECT
        o.clave AS obra_id,
        COALESCE(SUM(i.monto_recibido), 0) AS total_ingresos
    FROM main_staging.stg_dim_obras o
    LEFT JOIN main_staging.stg_fact_ingreso i ON o.airtable_id = i.obra_id
    GROUP BY o.clave
)

SELECT
    g.obra_id,
    g.nombre_obra,
    g.estado_obra,
    g.monto_contrato,
    g.total_materiales,
    p.total_mano_obra,
    g.total_materiales + p.total_mano_obra AS total_gastos,
    i.total_ingresos,
    i.total_ingresos - (g.total_materiales + p.total_mano_obra) AS resultado_neto,
    CASE
        WHEN g.monto_contrato > 0
        THEN ROUND((g.total_materiales + p.total_mano_obra) / g.monto_contrato * 100, 2)
        ELSE NULL
    END AS pct_contrato_ejecutado,
    CASE
        WHEN i.total_ingresos > (g.total_materiales + p.total_mano_obra) THEN 'RENTABLE'
        WHEN i.total_ingresos > 0 THEN 'DEFICIT'
        ELSE 'SIN INGRESOS'
    END AS estado_financiero,
    RANK() OVER (ORDER BY i.total_ingresos - (g.total_materiales + p.total_mano_obra) DESC) AS ranking_rentabilidad
FROM gastos_obra g
LEFT JOIN pagos_obra p ON g.obra_id = p.obra_id
LEFT JOIN ingresos_obra i ON g.obra_id = i.obra_id
WHERE g.total_materiales + p.total_mano_obra > 0
ORDER BY resultado_neto DESC;
