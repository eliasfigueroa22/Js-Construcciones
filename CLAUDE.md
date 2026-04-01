# JS Tools — Streamlit Admin Panel

## Project Overview
Internal admin panel ("JS Tools") for **JS Construcciones**, a construction company in Paraguay. Built with Streamlit, deployed on Streamlit Community Cloud. All UI in Spanish.

---

## On Session Start
**Always read `architecture.md` and `customization.md` before doing any work.** They contain the current file structure, patterns, Supabase schema, and how-to guides. Do not rely on memory alone.

---

## Current Status *(updated 2026-04-01)*

| Tool | File | Status |
|------|------|--------|
| Verificador de Facturas | `pages/01_verificador_facturas.py` | ✅ Complete |
| Resumen de Pagos | `pages/02_resumen_pagos.py` | ✅ Complete |
| Gestor de Duplicados | `pages/03_gestor_duplicados.py` | ✅ Complete |
| Reporte de Obra | `pages/04_reporte_obra.py` | ✅ Complete |
| Mediciones | `pages/05_mediciones.py` | ✅ Complete |
| Certificaciones | `pages/06_certificaciones.py` | ✅ Complete |
| Planilla de Pagos | `pages/07_planilla_pagos.py` | ✅ Complete |

**Infrastructure:** Core registry, **Supabase connector** (`get_all_records`, `create_record`, `update_record`, `delete_record`, `clear_cache`, `ttl=300`), sync engine (`connectors/sync.py` — Airtable→Supabase pull en batches), auth (`core/auth.py` — email/password, roles admin/operador/viewer, permisos por tool), PDF generator (`generate_report_pdf`, `generate_combined_report_pdf`, `generate_obra_report_pdf`, `generate_medicion_pdf`, `generate_certificado_memo_pdf`, `generate_certificado_detalle_pdf`, `generate_resumen_financiero_pdf`, `generate_planilla_pagos_pdf`), KuDE parser, logo (`assets/logo.png`) — all complete.

**Data source:** Supabase PostgreSQL — Kimball star schema, 26 tablas (`dim_*`, `fact_*`, `op_*`, `aux_*`, `bkp_*`). Airtable sigue siendo fuente de entrada; sync manual vía botón en sidebar. Todos los campos en snake_case, IDs son BIGINT.

---

## Project Plan

- **Phase 1** ✅ Core infrastructure (registry, connector, config, PDF generator)
- **Phase 2** ✅ Tool 1 — Invoice verifier (KuDE/PDF parsing, Airtable matching, reports)
- **Phase 3** ✅ Tool 2 — Payment summary (cascading filters, combined presupuesto+pago table, PDF/Excel export)
- **Phase 4** ✅ Tool 3 — Duplicate manager (invoice + line detection, false positive dismissal, PDF report)
- **Phase 5** ✅ Tool 4 — Obra report (hierarchical PDF: resumen + materiales + MO, logo header, page templates)
- **Phase 6** ✅ Tool 5 — Mediciones (weekly measurement sheets, Supabase sync, Borrador/Confirmado state, PDF/Excel)
- **Phase 7** ✅ Tool 6 — Certificaciones (presupuesto por obra, certificaciones periódicas, memo PDF + planilla detallada landscape, Excel)
- **Phase 8** ✅ Tool 7 — Planilla de Pagos (planilla semanal por obra, context card por trabajador, PDF export, carga selectiva a fact_pago)
- **Phase 9** ✅ Migración Airtable → Supabase (schema Kimball, sync engine, auth con roles, migración de las 7 páginas)
- **Phase 10+** 🔲 Future tools (to be defined)

---

## Working Rules
- **Only change what was explicitly asked.** If a request touches something adjacent, ask first.
- **Ask before acting** on anything with unclear scope.
- See `customization.md` for UI conventions and patterns to follow when building new tools.
