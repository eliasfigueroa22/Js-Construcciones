-- ============================================================================
-- Monthly spend trend with month-over-month variation
-- Demonstrates: DATE_TRUNC, UNION ALL, LAG window function, YTD accumulation
-- ============================================================================
WITH materiales_mensual AS (
    SELECT
        DATE_TRUNC('month', fecha_compra) AS mes,
        'MATERIALES' AS tipo_gasto,
        SUM(monto_total) AS monto
    FROM main_staging.stg_fact_compra
    GROUP BY DATE_TRUNC('month', fecha_compra)
),

mano_obra_mensual AS (
    SELECT
        DATE_TRUNC('month', fecha_pago) AS mes,
        'MANO_DE_OBRA' AS tipo_gasto,
        SUM(monto_pago) AS monto
    FROM main_staging.stg_fact_pago
    GROUP BY DATE_TRUNC('month', fecha_pago)
),

ingresos_mensual AS (
    SELECT
        DATE_TRUNC('month', fecha_ingreso) AS mes,
        'INGRESOS' AS tipo_gasto,
        SUM(monto_recibido) AS monto
    FROM main_staging.stg_fact_ingreso
    WHERE fecha_ingreso IS NOT NULL
    GROUP BY DATE_TRUNC('month', fecha_ingreso)
),

combined AS (
    SELECT * FROM materiales_mensual
    UNION ALL
    SELECT * FROM mano_obra_mensual
    UNION ALL
    SELECT * FROM ingresos_mensual
)

SELECT
    mes,
    tipo_gasto,
    monto,
    LAG(monto) OVER (PARTITION BY tipo_gasto ORDER BY mes) AS monto_mes_anterior,
    ROUND(
        (monto - LAG(monto) OVER (PARTITION BY tipo_gasto ORDER BY mes))
        / NULLIF(LAG(monto) OVER (PARTITION BY tipo_gasto ORDER BY mes), 0) * 100, 2
    ) AS variacion_pct,
    SUM(monto) OVER (
        PARTITION BY tipo_gasto, EXTRACT(YEAR FROM mes)
        ORDER BY mes
    ) AS acumulado_ytd
FROM combined
ORDER BY mes, tipo_gasto;
