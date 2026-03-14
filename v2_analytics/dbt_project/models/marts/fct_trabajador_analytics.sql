with pagos as (
    select * from {{ ref('int_pagos_enriched') }}
),

trabajadores as (
    select airtable_id, nombre_completo
    from {{ ref('stg_dim_trabajador') }}
),

deudas as (
    select
        t.nombre_completo as trabajador_id,
        count(*) as qty_deudas,
        sum(case when d.estado = 'ACTIVO' then d.monto_deuda else 0 end) as deuda_activa,
        sum(case when d.estado = 'PAGADO' then d.monto_deuda else 0 end) as deuda_pagada
    from {{ ref('stg_fact_deuda') }} d
    left join trabajadores t on d.trabajador_id = t.airtable_id
    group by t.nombre_completo
),

pago_stats as (
    select
        trabajador_id,
        tipo_personal,
        count(*) as qty_pagos,
        count(distinct obra_id) as qty_obras,
        sum(monto_pago) as total_pagado,
        sum(case when tipo_pago = 'ADELANTO' then monto_pago else 0 end) as total_adelantos,
        sum(case when tipo_pago = 'PAGO' then monto_pago else 0 end) as total_pagos_regulares,
        min(fecha_pago) as primer_pago,
        max(fecha_pago) as ultimo_pago
    from pagos
    group by trabajador_id, tipo_personal
)

select
    ps.trabajador_id,
    ps.tipo_personal,
    ps.qty_pagos,
    ps.qty_obras,
    ps.total_pagado,
    ps.total_adelantos,
    ps.total_pagos_regulares,
    ps.primer_pago,
    ps.ultimo_pago,
    coalesce(d.qty_deudas, 0) as qty_deudas,
    coalesce(d.deuda_activa, 0) as deuda_activa,
    coalesce(d.deuda_pagada, 0) as deuda_pagada,
    round(ps.total_adelantos / nullif(ps.total_pagado, 0) * 100, 2) as pct_adelantos,
    rank() over (order by ps.total_pagado desc) as ranking_pagos
from pago_stats ps
left join deudas d on ps.trabajador_id = d.trabajador_id
order by ps.total_pagado desc
