-- ============================================================================
-- Worker productivity and financial analysis
-- Demonstrates: Multiple aggregations, date arithmetic, CASE, LEFT JOIN, COALESCE
-- ============================================================================
WITH pago_stats AS (
    SELECT
        t.nombre_completo AS trabajador,
        t.tipo_personal,
        COUNT(*) AS qty_pagos,
        COUNT(DISTINCT p.obra_id) AS qty_obras,
        SUM(p.monto_pago) AS total_pagado,
        SUM(CASE WHEN p.tipo_pago = 'ADELANTO' THEN p.monto_pago ELSE 0 END) AS total_adelantos,
        SUM(CASE WHEN p.tipo_pago = 'PAGO' THEN p.monto_pago ELSE 0 END) AS total_pagos_regulares,
        MIN(p.fecha_pago) AS primer_pago,
        MAX(p.fecha_pago) AS ultimo_pago,
        -- Months active
        DATEDIFF('month', MIN(p.fecha_pago), MAX(p.fecha_pago)) + 1 AS meses_activo
    FROM main_staging.stg_fact_pago p
    LEFT JOIN main_staging.stg_dim_trabajador t ON p.trabajador_id = t.airtable_id
    GROUP BY t.nombre_completo, t.tipo_personal
),

deuda_stats AS (
    SELECT
        t.nombre_completo AS trabajador,
        COUNT(*) AS qty_deudas,
        SUM(CASE WHEN d.estado = 'ACTIVO' THEN d.monto_deuda ELSE 0 END) AS deuda_activa,
        SUM(CASE WHEN d.estado = 'PAGADO' THEN d.monto_deuda ELSE 0 END) AS deuda_pagada
    FROM main_staging.stg_fact_deuda d
    LEFT JOIN main_staging.stg_dim_trabajador t ON d.trabajador_id = t.airtable_id
    GROUP BY t.nombre_completo
)

SELECT
    ps.trabajador,
    ps.tipo_personal,
    ps.qty_pagos,
    ps.qty_obras,
    ps.meses_activo,
    ps.total_pagado,
    ps.total_pagos_regulares,
    ps.total_adelantos,
    ROUND(ps.total_adelantos / NULLIF(ps.total_pagado, 0) * 100, 2) AS pct_adelantos,
    -- Average monthly earnings
    ROUND(ps.total_pagado / NULLIF(ps.meses_activo, 0), 0) AS promedio_mensual,
    COALESCE(ds.qty_deudas, 0) AS qty_deudas,
    COALESCE(ds.deuda_activa, 0) AS deuda_activa,
    ps.primer_pago,
    ps.ultimo_pago,
    RANK() OVER (ORDER BY ps.total_pagado DESC) AS ranking_pagos
FROM pago_stats ps
LEFT JOIN deuda_stats ds ON ps.trabajador = ds.trabajador
ORDER BY ps.total_pagado DESC;
