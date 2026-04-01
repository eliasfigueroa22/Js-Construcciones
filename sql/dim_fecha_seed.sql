-- =============================================================================
-- Seed: dim_fecha — 2018-01-01 a 2035-12-31
-- Genera ~6,574 filas con generate_series (sin INSERT manuales)
-- Los nombres de día/mes se guardan en inglés desde PostgreSQL;
-- la traducción al español se hace en la capa app con el dict MESES_ES / DIAS_ES
-- en config.py.
-- =============================================================================

INSERT INTO public.dim_fecha (
    fecha,
    anio,
    mes,
    dia,
    trimestre,
    semana_iso,
    nombre_dia,
    nombre_mes,
    es_fin_semana
)
SELECT
    d::DATE                                         AS fecha,
    EXTRACT(YEAR    FROM d)::SMALLINT               AS anio,
    EXTRACT(MONTH   FROM d)::SMALLINT               AS mes,
    EXTRACT(DAY     FROM d)::SMALLINT               AS dia,
    EXTRACT(QUARTER FROM d)::SMALLINT               AS trimestre,
    EXTRACT(WEEK    FROM d)::SMALLINT               AS semana_iso,
    TO_CHAR(d, 'Day')                               AS nombre_dia,   -- 'Monday   '
    TO_CHAR(d, 'Month')                             AS nombre_mes,   -- 'January  '
    EXTRACT(DOW FROM d) IN (0, 6)                   AS es_fin_semana
FROM generate_series(
    '2018-01-01'::DATE,
    '2035-12-31'::DATE,
    '1 day'::INTERVAL
) AS d
ON CONFLICT (fecha) DO NOTHING;
