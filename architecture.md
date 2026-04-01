# JS Tools — Architecture

## File Structure

| File | Role |
|------|------|
| `app.py` | Home page + `st.navigation()` wiring. Auth gate (`require_auth()`), sidebar sync button (`run_full_sync()`), tool filtering by user permissions. Auto-discovers tools via registry. |
| `core/registry.py` | Scans `pages/` with `ast.parse()` to extract `TOOL = ToolMetadata(...)` without executing page code. |
| `core/base_tool.py` | `ToolMetadata` frozen dataclass: `name`, `description`, `icon`, `page_file`. |
| `core/auth.py` | `login()`, `logout()`, `require_auth()`, `get_current_role()`, `get_tool_permissions()`. Uses Supabase Auth (email/password). |
| `config.py` | Secrets via `st.secrets` or `.env`. `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`. `SUPABASE_TABLES` dict maps readable key → Postgres table name. |
| `connectors/supabase_connector.py` | `get_all_records(table)`, `create_record(table, fields)`, `update_record(table, id, fields)`, `delete_record(table, id)`, `clear_cache()`. Cache `ttl=300` (5 min). |
| `connectors/sync.py` | `run_full_sync()`, `sync_table()`, `build_id_map()`, `_map_<tabla>()` per table. Pulls Airtable → Supabase via upsert on `airtable_id`. |
| `parsers/pdf_parser.py` | KuDE/PDF parsing. `_extract_emisor_name()` gets seller name from before first "Dirección:". |
| `generators/pdf_generator.py` | `generate_report_pdf()`, `generate_combined_report_pdf()`, `generate_obra_report_pdf()`, `generate_medicion_pdf()`, `generate_certificado_memo_pdf()`, `generate_certificado_detalle_pdf()`, `generate_resumen_financiero_pdf()`, `generate_planilla_pagos_pdf()` via reportlab. |
| `assets/logo.png` | Logo de JS Construcciones. Usado en el header de los PDFs de obra. |
| `sql/schema.sql` | DDL completo: CREATE TABLE, índices, RLS policies, triggers `set_updated_at()`. |
| `sql/dim_fecha_seed.sql` | INSERT de `dim_fecha` vía `generate_series('2018-01-01','2035-12-31','1 day')`. |
| `pages/01_verificador_facturas.py` | Tool 1: invoice verifier. |
| `pages/02_resumen_pagos.py` | Tool 2: payment summary per worker/obra. |
| `pages/03_gestor_duplicados.py` | Tool 3: duplicate detector + deletion for fact_compra. |
| `pages/04_reporte_obra.py` | Tool 4: obra report — resumen + materiales + MO, PDF exportable. |
| `pages/05_mediciones.py` | Tool 5: planilla de mediciones — 2 tabs: ✏️ Editar (cabecera + líneas, sync Supabase, PDF/Excel) + 📊 Vista General (acumulado filtrable, PDF/Excel). |
| `pages/06_certificaciones.py` | Tool 6: certificaciones de obra — 3 tabs: 📝 Presupuesto (CRUD + import Excel + copiar + eliminar) + 📋 Certificaciones (avance periódico, cálculos automáticos, eliminar cert, memo/detalle PDF descarga directa, Excel) + 📊 Resumen (cuadre financiero por obra: presupuesto vs certificado vs cobrado, timeline, PDF exportable). |
| `pages/07_planilla_pagos.py` | Tool 7: planilla semanal de pagos — 2 tabs: ✏️ Planilla (form de agregar pagos, context card por trabajador, tabla agrupada por obra con checkboxes, PDF export, carga selectiva a fact_pago) + 📊 Consultar Trabajador (historial de retiros, presupuesto activo, mediciones). |

---

## Supabase Schema

**Proyecto:** `JsConstrucciones` · región `sa-east-1`

### Prefijos de tablas

| Prefijo | Tipo | Descripción |
|---------|------|-------------|
| `dim_*` | Dimensión | Catálogos maestros (SCD Type 1 — overwrite) |
| `fact_*` | Hecho | Transacciones y registros financieros |
| `op_*` | Operacional | Mediciones y certificaciones (cabecera + líneas) |
| `aux_*` | Auxiliar | Falsos duplicados, log de sync |
| `bkp_*` | Backup | Datos de uso personal archivados, no usados en la app |

### Convenciones globales
- Surrogate keys: `id BIGSERIAL PRIMARY KEY`
- Natural key Airtable: `airtable_id TEXT UNIQUE NOT NULL` en toda tabla sincronizada
- `updated_at TIMESTAMPTZ DEFAULT now()` en todas las tablas
- `ON DELETE RESTRICT` en todos los FKs (excepto `user_tool_permissions` → CASCADE)
- Montos en Guaraníes: `NUMERIC(18,0)` · Cantidades/dimensiones: `NUMERIC(15,3)`

### Tablas

#### Auth
| Tabla | Descripción |
|-------|-------------|
| `user_profiles` | Extiende `auth.users`: nombre, email, role (`admin`\|`operador`\|`viewer`), activo |
| `user_tool_permissions` | `user_id` + `tool_slug` + `can_access`. ON DELETE CASCADE. |

Tool slugs: `verificador_facturas`, `resumen_pagos`, `gestor_duplicados`, `reporte_obra`, `mediciones`, `certificaciones`, `planilla_pagos`

#### Dimensiones
| Tabla | FK | Descripción |
|-------|----|-------------|
| `dim_fecha` | — | Fechas 2018–2035, pre-poblada. No referenciada por FK. |
| `dim_cliente` | — | Clientes |
| `dim_obra` | → `dim_cliente` | Obras/proyectos. Entidad central. |
| `dim_rubro` | — | Categorías de trabajo (ALB, REV, etc.) |
| `dim_sector` | → `dim_obra` | Subdivisiones físicas de una obra |
| `dim_trabajador` | → `dim_rubro` | Subcontratistas/trabajadores, con rubro principal |
| `dim_proveedor` | — | Proveedores de materiales |

#### Hechos
| Tabla | FKs principales | Grain |
|-------|----------------|-------|
| `fact_compra` | `dim_obra` (nullable), `dim_sector`, `dim_rubro`, `dim_proveedor` (nullable) + `proveedor_texto` | una línea de compra |
| `fact_pago` | `dim_obra` **NOT NULL**, `dim_trabajador` **NOT NULL**, `dim_sector`, `dim_rubro`, `fact_presupuesto_subcontratista` (nullable) | un pago a trabajador |
| `fact_presupuesto_subcontratista` | `dim_trabajador`, `dim_obra`, `dim_sector`, `dim_rubro` | un acuerdo presupuestario |
| `fact_facturacion_subcontratista` | → `fact_presupuesto_subcontratista` | una factura de subcontratista |
| `fact_presupuesto_cliente` | `dim_obra`, `dim_sector`, `dim_rubro` | una línea de presupuesto al cliente |
| `fact_ingreso` | → `dim_obra` | un cobro recibido del cliente |
| `fact_deuda` | `dim_obra`, `dim_trabajador` | un registro de deuda. `tipo_deuda TEXT CHECK IN ('ADELANTO_PERSONAL','COMPRA_PERSONAL','PRESTAMO')` |
| `fact_pago_deuda` | → `fact_deuda` (NOT NULL) | un pago que cancela deuda |

#### Operacionales
| Tabla | FKs | Descripción |
|-------|-----|-------------|
| `op_cert_presupuesto_linea` | `dim_obra`, `dim_rubro` + `rubro_texto` | Ítems del contrato de certificación (Zona → Grupo → Rubro) |
| `op_cert_cabecera` | → `dim_obra` | Cabecera de una certificación periódica. Estado: Borrador/Confirmado |
| `op_cert_linea` | → `op_cert_cabecera` (NOT NULL), → `op_cert_presupuesto_linea` | Cantidades certificadas por ítem |
| `op_medicion_cabecera` | `dim_obra`, `dim_trabajador` | Cabecera de planilla semanal de medición |
| `op_medicion_linea` | → `op_medicion_cabecera` (NOT NULL), `dim_sector`, `dim_rubro` | Líneas con dimensiones (L×A×H) |

#### Auxiliares
| Tabla | Descripción |
|-------|-------------|
| `aux_falsos_duplicados` | Grupos de facturas marcados como "no son duplicados" |
| `aux_sync_log` | Log de cada sync: tabla, timestamps, records_upserted, status, error_message |

### Row Level Security

| Operación | viewer | operador | admin |
|-----------|--------|----------|-------|
| SELECT | ✅ | ✅ | ✅ |
| INSERT | ❌ | ✅ | ✅ |
| UPDATE | ❌ | ✅ | ✅ |
| DELETE | ❌ | ❌ | ✅ |

- `aux_sync_log`: solo admin SELECT; service_role escribe (bypassa RLS)
- `user_profiles`: cada usuario ve solo el suyo; admin ve todos

---

## Sync Airtable → Supabase

**Estrategia:** Airtable es solo fuente de entrada. La app lee TODO desde Supabase. El botón "Sincronizar" en el sidebar hace el pull completo.

**Orden de dependencias (batches):**
```
Batch 1: dim_cliente, dim_rubro, dim_proveedor
Batch 2: dim_obra, dim_trabajador
Batch 3: dim_sector
Batch 4: fact_presupuesto_subcontratista, fact_compra, fact_presupuesto_cliente, fact_ingreso, fact_deuda
Batch 5: fact_pago, fact_facturacion_subcontratista, fact_pago_deuda
Batch 6: op_cert_presupuesto_linea, op_medicion_cabecera
Batch 7: op_medicion_linea, op_cert_cabecera
Batch 8: op_cert_linea
Batch 9: aux_falsos_duplicados
Batch 10: bkp_compra_personal, bkp_proveedor_personal
```

**Resolución de IDs:** durante el sync se mantiene un `id_map: dict[str, dict[str, int]]` en memoria. Cada tabla dim/op se popula después de upsertear: `SELECT id, airtable_id FROM <tabla>`. `resolve_id(rec_id, "dim_obra")` retorna el BIGINT o `None`. Si `None` en FK NOT NULL → se loguea en `aux_sync_log.error_message` y se saltea el registro.

---

## Key Patterns

### Connector & Caching
- `get_all_records(table_name)` — `@st.cache_data(ttl=300)`. Se invalida con `clear_cache()`.
- `clear_cache()` en `supabase_connector.py` reemplaza el patrón anterior de `get_all_records.clear()` + `_load_*.clear()`.
- IDs son integers (`BIGINT`). No hay strings `"recXXX"` en Supabase.
- Campos en snake_case. No hay `_normalize()` ni `get_record_names()` — se construyen dicts `{id: nombre}` inline desde las tablas dim.
- FKs en writes se pasan como integer directo (sin list wrapping).

### Resolución de nombres en páginas
```python
# Patrón estándar en todas las páginas:
obras_raw = get_all_records("dim_obra")
nm_obra = {r["id"]: r.get("clave") or r.get("nombre", str(r["id"])) for r in obras_raw}
# Lookup:
nombre = nm_obra.get(alguna_obra_id, "—")
```

### PDF Generation (all tools)
- **Margins (Tools 1–3):** left=30mm, right=20mm, top=25mm, bottom=25mm.
- **Margins (Tool 4 — obra reports):** left=30mm, right=20mm, top=30mm, bottom=20mm (extra top para logo+header).
- `available_width = A4[0] - 50 * mm`
- `Paragraph` objects previenen text overlap. Columns auto-scale si total > available width.
- Formato guaraníes: `f"₲ {int(value):,}".replace(",", ".")`.
- Logo: `assets/logo.png` (project root). Dibujado en `(30mm, A4[1]−18mm)`, 28×11mm, `preserveAspectRatio=True`.

### PDF Generation — Obra Reports (Tool 4)
- Usa `BaseDocTemplate` + un `PageTemplate` por sección (nunca `SimpleDocTemplate`).
- Secciones: `"resumen"` / `"materiales"` / `"mo"` — cada una con su propio `onPage` callback.
- Switch secciones: `NextPageTemplate("materiales")` + `PageBreak()` en el story.
- `_NumberedCanvas` escribe "Página X de Y" interceptando `showPage()` y `save()`.
- `generate_medicion_pdf()` — Tool 5 PDF. Sector→Rubro hierarchy, S/P para precios sin definir.
- `generate_acumulado_pdf()` — Tool 5 vista acumulada. Rubro→ítems, columnas: Descripción / Ud / Cant.Total / P.U.Último / Total Acum.
- Ítems con el mismo `descripcion` dentro del mismo Sector/Rubro se agregan (sum cantidad + monto_total) antes de renderizar.

### PDF Generation — Certificaciones (Tool 6)
- `generate_certificado_memo_pdf()` — portrait A4. De/A, tablas por obra, total, "Son Guaraníes" en letras, firma.
- `generate_certificado_detalle_pdf()` — **landscape A4**. `_cert_page_template_landscape()` + `_NumberedCanvasLandscape`. Zona (naranja) → Grupo (gris-azul) → Rubro con tagged row pattern (`__meta__`).
- `generate_resumen_financiero_pdf()` — portrait A4. Métricas 3 columnas + balances + timeline table.
- `_guaranies_en_letras(monto)` — convierte integer a texto en español (documentos financieros paraguayos).

### Tool 1 — Tab Independence
- 4 input tabs (KuDE, Archivo, Lista, Excel/CSV), cada una completamente independiente.
- `_activate_source()` / `_deactivate_source()` controlan el tab activo.
- `_render_workflow(source)` renderiza config + resultados DENTRO del tab activo.
- `SEARCH_TABLES` dict define por tabla: columns, date_col, fk_cols para resolución de nombres.

### Tool 1 — Invoice Matching
- PDF tiene números cortos ("86285"), Supabase tiene "001-004-0086285".
- `_normalize_invoice_number()` strip prefix para matching.
- KuDE seller name: `_extract_emisor_name()` escanea hacia atrás desde la primera línea "Dirección:".

### Tool 2 — Cascading Filters (4 levels)
Estado de obra → Tipo/Categoría → Nombre de obra ("Todas las obras") → Personal.
Cada nivel solo muestra opciones que tienen registros `fact_pago` reales.

### Tool 2 — Combined Detail Table
- Un solo `st.dataframe` mostrando presupuestos + pagos juntos.
- Dos columnas de dinero: **Presupuesto (Gs.)** luego **Pago (Gs.)**.
- `_DETAIL_COLUMNS` list controla widths en PDF y en web. Cambiar una vez → ambos se actualizan.

### Tool 3 — Duplicate Detection
- **Invoice detector:** agrupa por `(nro_factura_norm, proveedor_texto, fecha)` → suma `monto_total`.
- **Line detector:** dentro de la misma entrada, marca líneas con igual `monto_total`.
- `_normalize_nro_doc()` padea a `NNN-NNN-NNNNNNN`.
- False positive dismissal: guarda `clave_grupo` en `aux_falsos_duplicados`.

### Tool 7 — Planilla de Pagos
- Estado en memoria (`pago_fecha: date`, `pago_lineas: list[dict]`) — sin persistencia entre sesiones.
- Cada línea dict: `{uid, obra_id, trab_id, concepto, monto, metodo, tipo_pago, include, saved_to_db}`. `uid = uuid4().hex`.
- Context card: computa retiro acumulado, presupuesto activo, balance, total última medición — todo desde caché, cero queries extra.
- Después de Cargar a BD: `saved_to_db=True` + `include=False` → fila muestra 🔒.
- `tipo_pago` CHECK: `PAGO`, `ADELANTO`, `PRODUCCION`.

---

## Tech Stack
Python 3.11+, Streamlit >=1.36, supabase-py >=2.4.0, pyairtable (solo para sync), pdfplumber, reportlab, pandas, openpyxl, python-dotenv
