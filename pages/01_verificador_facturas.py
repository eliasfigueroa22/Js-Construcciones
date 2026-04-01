"""Verificador de Facturas — compara valores de entrada contra Supabase.

Flujo:
1. El usuario ingresa valores (PDF, texto manual, o Excel/CSV).
2. Selecciona tabla y campo de Supabase contra el cual buscar.
3. Se muestran los resultados con las columnas seleccionadas.
4. Se ofrece descarga de reportes PDF.
"""

from datetime import date, datetime

import pandas as pd
import streamlit as st
from streamlit_sortables import sort_items

from core.base_tool import ToolMetadata
from connectors.supabase_connector import get_all_records
from generators.pdf_generator import generate_combined_report_pdf, generate_report_pdf
from parsers.pdf_parser import (
    extract_column_from_pdf,
    extract_multiple_kudes,
    extract_pdf_columns,
)

# -- Metadatos (leídos por registry.py vía AST, no ejecutados) ----------------
TOOL = ToolMetadata(
    name="Verificador de Facturas",
    description="Verificá facturas de proveedores contra los registros en la base de datos.",
    icon="🧾",
    page_file="01_verificador_facturas.py",
)

# -- Tablas disponibles para búsqueda -----------------------------------------
# Cada tabla define: label, columns (disponibles para selección y búsqueda),
# date_col (para el filtro de fecha), fk_cols (columnas FK → clave en SUPABASE_TABLES).
SEARCH_TABLES: dict[str, dict] = {
    "fact_compra": {
        "label": "Compras (Facturas)",
        "columns": [
            "nro_factura", "proveedor_texto", "fecha", "descripcion",
            "cantidad", "unidad", "monto_total", "tipo_documento",
            "observaciones", "obra_id", "sector_id", "rubro_id",
        ],
        "date_col": "fecha",
        "fk_cols": {
            "obra_id":   "dim_obra",
            "sector_id": "dim_sector",
            "rubro_id":  "dim_rubro",
        },
    },
    "fact_pago": {
        "label": "Pagos",
        "columns": [
            "fecha_pago", "concepto", "monto_pago", "tipo_pago",
            "metodo_pago", "observaciones", "obra_id", "sector_id",
            "rubro_id", "trabajador_id",
        ],
        "date_col": "fecha_pago",
        "fk_cols": {
            "obra_id":       "dim_obra",
            "sector_id":     "dim_sector",
            "rubro_id":      "dim_rubro",
            "trabajador_id": "dim_trabajador",
        },
    },
    "fact_ingreso": {
        "label": "Ingresos",
        "columns": [
            "numero_factura", "fecha_ingreso", "fecha_factura", "tipo_ingreso",
            "concepto", "monto_facturado", "monto_recibido", "estado_cobro",
            "fecha_cobro", "metodo_pago", "observaciones", "obra_id",
        ],
        "date_col": "fecha_ingreso",
        "fk_cols": {"obra_id": "dim_obra"},
    },
    "fact_presupuesto_cliente": {
        "label": "Presupuesto Cliente",
        "columns": [
            "descripcion", "fecha_presupuesto", "tipo_presupuesto",
            "cantidad", "unidad", "precio_unitario", "monto_total",
            "estado", "observaciones", "obra_id", "sector_id", "rubro_id",
        ],
        "date_col": "fecha_presupuesto",
        "fk_cols": {
            "obra_id":   "dim_obra",
            "sector_id": "dim_sector",
            "rubro_id":  "dim_rubro",
        },
    },
    "fact_presupuesto_subcontratista": {
        "label": "Presupuesto Subcontratista",
        "columns": [
            "concepto", "fecha_presupuesto", "monto_presupuestado",
            "estado", "obra_id", "sector_id", "rubro_id", "trabajador_id",
        ],
        "date_col": "fecha_presupuesto",
        "fk_cols": {
            "obra_id":       "dim_obra",
            "sector_id":     "dim_sector",
            "rubro_id":      "dim_rubro",
            "trabajador_id": "dim_trabajador",
        },
    },
    "fact_deuda": {
        "label": "Deudas",
        "columns": [
            "tipo_deuda", "fecha_solicitud", "monto_deuda",
            "estado", "observaciones", "obra_id", "trabajador_id",
        ],
        "date_col": "fecha_solicitud",
        "fk_cols": {
            "obra_id":       "dim_obra",
            "trabajador_id": "dim_trabajador",
        },
    },
}

# Columnas de cada dim usada como FK → campo de nombre legible
_DIM_NAME_COL: dict[str, str] = {
    "dim_obra":       "clave",
    "dim_sector":     "nombre_sector",
    "dim_rubro":      "rubro",
    "dim_trabajador": "nombre_completo",
}


# -- Helpers -------------------------------------------------------------------
def _fmt_gs(value) -> str:
    """Formatea un número al estilo paraguayo: 1.234.567."""
    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


def _resolve_linked(value, names_map: dict) -> str:
    """Resuelve un ID (int o lista de ints) a nombre usando el lookup."""
    if isinstance(value, list):
        return ", ".join(str(names_map.get(v, v)) for v in value)
    if value in names_map:
        return str(names_map[value])
    return str(value) if value else "—"


def _is_numeric_field(records: list[dict], key: str) -> bool:
    """Detecta si un campo contiene valores numéricos."""
    for rec in records[:20]:
        val = rec.get(key, "")
        if val == "" or val is None:
            continue
        try:
            float(val)
            return True
        except (ValueError, TypeError):
            return False
    return False


def _parse_date(val) -> date | None:
    """Intenta parsear un valor como fecha ISO (YYYY-MM-DD)."""
    if not val:
        return None
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _normalize_invoice_number(raw: str) -> str:
    """Extrae el número significativo de una factura con formato NNN-NNN-NNNNNNN.

    "001-004-0086285" → "86285"
    "86285" → "86285" (ya normalizado)
    """
    raw = raw.strip()
    if "-" in raw:
        last_segment = raw.rsplit("-", 1)[-1]
        try:
            return str(int(last_segment))
        except ValueError:
            return raw
    # Sin guiones: quitar ceros a la izquierda
    try:
        return str(int(raw))
    except ValueError:
        return raw


def _build_index(
    records: list[dict], search_field: str
) -> dict[str, list[dict]]:
    """Pre-calcula un índice {numero_normalizado: [registros]}."""
    index: dict[str, list[dict]] = {}
    for rec in records:
        raw = str(rec.get(search_field, ""))
        key = _normalize_invoice_number(raw)
        if key:
            index.setdefault(key, []).append(rec)
    return index


def _match(
    input_values: list[str],
    records: list[dict],
    search_field: str,
    extra_fields: list[str],
    match_exact: bool,
    name_maps: dict[str, dict],
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    date_col: str = "fecha",
) -> tuple[list[dict], list[str], int]:
    """Cruza valores de entrada contra registros de Supabase."""
    found: list[dict] = []
    missing: list[str] = []
    skipped_no_fecha = 0
    date_filter_active = fecha_desde is not None or fecha_hasta is not None

    index = _build_index(records, search_field)

    for val in input_values:
        val_norm = _normalize_invoice_number(val)
        matches = index.get(val_norm, [])

        if date_filter_active and matches:
            filtered = []
            for m in matches:
                rec_date = _parse_date(m.get(date_col, ""))
                if rec_date is None:
                    skipped_no_fecha += 1
                    continue
                if fecha_desde and rec_date < fecha_desde:
                    continue
                if fecha_hasta and rec_date > fecha_hasta:
                    continue
                filtered.append(m)
            matches = filtered

        if not matches:
            missing.append(val)
            continue

        row: dict = {"_InputValue": val, search_field: matches[0].get(search_field, val)}

        for fk in extra_fields:
            raw_values = [m.get(fk, "") for m in matches if m.get(fk, "") not in ("", None)]
            if not raw_values:
                row[fk] = "—"
                continue
            nmap = name_maps.get(fk)
            if nmap:
                resolved = set()
                for rv in raw_values:
                    resolved.add(_resolve_linked(rv, nmap))
                row[fk] = ", ".join(sorted(resolved))
            elif _is_numeric_field(records, fk):
                row[fk] = sum(float(v or 0) for v in raw_values)
            else:
                unique = sorted({str(v) for v in raw_values})
                row[fk] = ", ".join(unique)

        row["CantRegistros"] = len(matches)
        found.append(row)

    return found, missing, skipped_no_fecha


# -- CSS ----------------------------------------------------------------------
st.markdown("""
<style>
:root {
    --js-accent:  #E8622A;
    --js-success: #27AE60;
    --js-danger:  #E74C3C;
    --js-warn:    #E67E22;
    --js-muted:   #6B7280;
    --js-border:  rgba(255,255,255,0.09);
    --js-surface: rgba(255,255,255,0.03);
}
.js-sub {
    color: var(--js-muted);
    font-size: .875rem;
    margin-top: -10px;
    margin-bottom: 24px;
}
.js-pill {
    display: inline-block;
    border-radius: 3px;
    padding: 2px 8px;
    font-size: .68rem;
    font-weight: 700;
    letter-spacing: .8px;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.js-found   { background: rgba(39,174,96,.12);  color: #27AE60; border: 1px solid rgba(39,174,96,.2); }
.js-missing { background: rgba(231,76,60,.12);  color: #E74C3C; border: 1px solid rgba(231,76,60,.2); }
</style>
""", unsafe_allow_html=True)

# -- UI principal --------------------------------------------------------------
st.title("🧾 Verificador de Facturas")
st.markdown(
    '<p class="js-sub">Verificá facturas de proveedores contra los registros en la base de datos</p>',
    unsafe_allow_html=True,
)


def _clear_results():
    """Limpia resultados de verificación."""
    for k in ("found_invoices", "missing_invoices", "_skipped_no_fecha",
              "_result_extra_fields", "_result_search_field",
              "_result_table", "_result_fecha_desde", "_result_fecha_hasta"):
        st.session_state.pop(k, None)


def _activate_source(source: str, values: list[str]):
    """Establece una fuente como activa y carga sus valores."""
    prev = st.session_state.get("_active_source")
    st.session_state["_active_source"] = source
    st.session_state["_input_values"] = values
    if prev != source:
        _clear_results()


def _deactivate_source(source: str):
    """Desactiva una fuente si es la activa y limpia resultados."""
    if st.session_state.get("_active_source") == source:
        st.session_state.pop("_active_source", None)
        st.session_state.pop("_input_values", None)
        _clear_results()


# -- Flujo de verificación (se renderiza dentro de cada tab) -------------------
def _render_workflow(source: str):
    """Renderiza config + verificación + resultados + descargas dentro del tab activo."""
    input_values = st.session_state.get("_input_values", [])
    if st.session_state.get("_active_source") != source or not input_values:
        return

    st.divider()
    st.subheader("2. Configuración de búsqueda")

    table_keys = list(SEARCH_TABLES.keys())
    selected_table = st.selectbox(
        "Tabla",
        table_keys,
        format_func=lambda k: SEARCH_TABLES[k]["label"],
        key=f"{source}_table_select",
    )

    tbl_cfg = SEARCH_TABLES[selected_table]
    available_fields = tbl_cfg["columns"]
    search_field = st.selectbox(
        "Campo donde buscar", available_fields,
        key=f"{source}_search_field",
    )

    other_fields = [f for f in available_fields if f != search_field]

    _col_key = f"_col_order_01_{source}"
    _fields_sig = tuple(other_fields)
    if st.session_state.get(f"_col_sig_01_{source}") != _fields_sig:
        st.session_state[f"_col_sig_01_{source}"] = _fields_sig
        st.session_state[_col_key] = list(other_fields)

    with st.popover("⚙️ Columnas adicionales"):
        for _f in other_fields:
            _checked = _f in st.session_state[_col_key]
            if st.checkbox(_f, value=_checked, key=f"chk_01_{source}_{_f}"):
                if not _checked:
                    st.session_state[_col_key].append(_f)
            else:
                if _checked:
                    st.session_state[_col_key].remove(_f)

    _cur = st.session_state[_col_key]
    if _cur:
        st.caption("Arrastrá para reordenar")
        _cur = sort_items(_cur, key=f"sort_01_{source}_{abs(hash(frozenset(_cur)))}")
        st.session_state[_col_key] = _cur
    extra_fields = _cur

    fecha_desde: date | None = None
    fecha_hasta: date | None = None
    with st.expander("📅 Filtrar por rango de fechas", expanded=True):
        st.caption(
            "Útil para evitar duplicados cuando el mismo número "
            "de factura aparece en distintos períodos o proveedores."
        )
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            fd = st.date_input("Desde", value=None, key=f"{source}_fecha_desde", format="DD/MM/YYYY")
        with fcol2:
            fh = st.date_input("Hasta", value=None, key=f"{source}_fecha_hasta", format="DD/MM/YYYY")
        if fd:
            fecha_desde = fd
        if fh:
            fecha_hasta = fh

    if st.button("🔍 Verificar", type="primary", use_container_width=True, key=f"{source}_verify"):
        try:
            with st.spinner("Consultando base de datos..."):
                records = get_all_records(selected_table)

                # Construir name_maps para columnas FK seleccionadas
                fk_cols = tbl_cfg.get("fk_cols", {})
                name_maps: dict[str, dict] = {}
                for fk in extra_fields:
                    if fk in fk_cols:
                        dim_key = fk_cols[fk]
                        name_col = _DIM_NAME_COL.get(dim_key, "id")
                        dim_recs = get_all_records(dim_key)
                        name_maps[fk] = {
                            r["id"]: r.get(name_col, str(r["id"]))
                            for r in dim_recs
                        }

            found, missing, skipped = _match(
                input_values, records, search_field, extra_fields,
                False, name_maps, fecha_desde, fecha_hasta,
                date_col=tbl_cfg.get("date_col", "fecha"),
            )
            st.session_state["found_invoices"] = found
            st.session_state["missing_invoices"] = missing
            st.session_state["_skipped_no_fecha"] = skipped
            st.session_state["_result_extra_fields"] = extra_fields
            st.session_state["_result_search_field"] = search_field
            st.session_state["_result_table"] = selected_table
            st.session_state["_result_fecha_desde"] = fecha_desde
            st.session_state["_result_fecha_hasta"] = fecha_hasta
        except ConnectionError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Error inesperado al verificar: {exc}")

    # == Resultados ============================================================
    found = st.session_state.get("found_invoices")
    missing = st.session_state.get("missing_invoices")

    if found is None or missing is None:
        return

    r_extra = st.session_state.get("_result_extra_fields", [])
    r_search = st.session_state.get("_result_search_field", "")

    st.divider()
    st.subheader("Resultados")

    skipped = st.session_state.get("_skipped_no_fecha", 0)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total ingresados", len(found) + len(missing))
    col2.metric("Encontrados", len(found))
    col3.metric("No encontrados", len(missing))

    if skipped > 0:
        st.warning(f"**{skipped}** registro(s) ignorado(s) por no tener fecha registrada.")

    if found:
        st.markdown('<span class="js-pill js-found">Encontrados</span>', unsafe_allow_html=True)
        df_found = pd.DataFrame(found)
        display_cols = [r_search] + [f for f in r_extra if f in df_found.columns]
        df_display = df_found[display_cols].copy()

        col_config: dict = {}
        for col_name in display_cols:
            if df_display[col_name].dtype in ("float64", "int64", "float32", "int32"):
                is_monto = "monto" in col_name.lower() or "total" in col_name.lower() or "precio" in col_name.lower()
                if is_monto:
                    df_display[col_name] = df_display[col_name].apply(
                        lambda v: _fmt_gs(v) if pd.notna(v) and v != "" else "—"
                    )
                    col_config[col_name] = st.column_config.TextColumn(col_name)

        st.dataframe(df_display, use_container_width=True, hide_index=True, column_config=col_config)

    if missing:
        st.markdown('<span class="js-pill js-missing">No encontrados en la base de datos</span>', unsafe_allow_html=True)

        is_kude = source == "kude"
        kude_data = st.session_state.get("_kude_data", []) if is_kude else []
        kude_lookup = {
            k["numero_simple"]: k for k in kude_data if k.get("numero_simple")
        } if kude_data else {}

        missing_rows = []
        for val in missing:
            row = {"Valor": val}
            kude = kude_lookup.get(val)
            if kude:
                row["Nro. Factura"] = kude.get("numero_factura", "—")
                row["Proveedor"] = kude.get("proveedor", "—")
                row["Fecha"] = str(kude["fecha"]) if kude.get("fecha") else "—"
                row["Monto Total (Gs.)"] = _fmt_gs(kude["monto_total"]) if kude.get("monto_total") else "—"
            missing_rows.append(row)

        df_missing = pd.DataFrame(missing_rows)
        st.dataframe(df_missing, use_container_width=True, hide_index=True)

    # == Descargar reportes ====================================================
    st.divider()
    st.subheader("Descargar reporte")

    today = datetime.now().strftime("%Y-%m-%d")
    r_table = st.session_state.get("_result_table", "")
    r_fecha_desde = st.session_state.get("_result_fecha_desde")
    r_fecha_hasta = st.session_state.get("_result_fecha_hasta")

    summary_info: dict[str, str] = {
        "Fecha del reporte": today,
        "Tabla": SEARCH_TABLES.get(r_table, {}).get("label", r_table),
        "Campo de búsqueda": r_search,
    }
    if r_fecha_desde:
        summary_info["Fecha desde"] = r_fecha_desde.strftime("%d/%m/%Y")
    if r_fecha_hasta:
        summary_info["Fecha hasta"] = r_fecha_hasta.strftime("%d/%m/%Y")
    summary_info["Total valores"] = str(len(found) + len(missing))
    summary_info["Encontrados"] = str(len(found))
    summary_info["No encontrados"] = str(len(missing))

    # Columnas encontrados
    found_report_cols = [{"key": r_search, "label": r_search, "width_mm": 35}]
    for fk in r_extra:
        is_money = "monto" in fk.lower() or "total" in fk.lower() or "precio" in fk.lower()
        found_report_cols.append({
            "key": fk, "label": fk, "width_mm": 30,
            **({"format": "guaranies"} if is_money else {}),
        })

    monto_key = next(
        (fk for fk in r_extra if "monto" in fk.lower() or "total" in fk.lower()),
        None,
    )
    found_subtotal = None
    if monto_key and found:
        try:
            found_subtotal = sum(float(r.get(monto_key, 0) or 0) for r in found)
        except (ValueError, TypeError):
            pass

    # Columnas no encontrados
    is_kude_dl = source == "kude"
    kude_data_dl = st.session_state.get("_kude_data", []) if is_kude_dl else []
    has_kude = bool(kude_data_dl)
    kude_lookup_dl = {
        k["numero_simple"]: k for k in kude_data_dl if k.get("numero_simple")
    } if has_kude else {}

    missing_rows_dl = []
    for val in missing:
        row = {"Valor": val}
        kude = kude_lookup_dl.get(val)
        if kude:
            row["NroFactura"] = kude.get("numero_factura", "")
            row["Proveedor"] = kude.get("proveedor", "")
            row["Fecha"] = str(kude["fecha"]) if kude.get("fecha") else ""
            row["MontoTotal"] = kude.get("monto_total", "")
        missing_rows_dl.append(row)

    missing_report_cols = [{"key": "Valor", "label": "Valor buscado", "width_mm": 25}]
    if has_kude:
        missing_report_cols += [
            {"key": "NroFactura", "label": "Nro. Factura", "width_mm": 35},
            {"key": "Proveedor", "label": "Proveedor", "width_mm": 50},
            {"key": "Fecha", "label": "Fecha", "width_mm": 22},
            {"key": "MontoTotal", "label": "Monto Total (Gs.)", "width_mm": 28, "format": "guaranies"},
        ]

    missing_subtotal = None
    if has_kude and missing:
        try:
            missing_subtotal = sum(
                float(kude_lookup_dl[val].get("monto_total", 0) or 0)
                for val in missing if val in kude_lookup_dl
            )
        except (ValueError, TypeError):
            pass

    grand_total = None
    if found_subtotal is not None or missing_subtotal is not None:
        grand_total = (found_subtotal or 0) + (missing_subtotal or 0)

    sections = [
        {"subtitle": f"Encontrados ({len(found)})", "columns": found_report_cols, "rows": found},
        {"subtitle": f"No encontrados ({len(missing)})", "columns": missing_report_cols, "rows": missing_rows_dl},
    ]

    pdf_combined = generate_combined_report_pdf(
        title=f"Verificación — {today}",
        sections=sections,
        summary=summary_info,
        grand_total=grand_total,
    )
    st.download_button(
        label="📥 Descargar reporte completo (PDF)",
        data=pdf_combined,
        file_name=f"verificacion_{today}.pdf",
        mime="application/pdf",
        key=f"{source}_dl_combined",
    )

    if missing:
        missing_summary: dict[str, str] = {
            "Fecha del reporte": today,
            "Tabla": SEARCH_TABLES.get(r_table, {}).get("label", r_table),
            "Campo de búsqueda": r_search,
        }
        if r_fecha_desde:
            missing_summary["Fecha desde"] = r_fecha_desde.strftime("%d/%m/%Y")
        if r_fecha_hasta:
            missing_summary["Fecha hasta"] = r_fecha_hasta.strftime("%d/%m/%Y")
        missing_summary["Total no encontrados"] = str(len(missing))
        if missing_subtotal is not None:
            missing_summary["Monto total (Gs.)"] = _fmt_gs(missing_subtotal)

        pdf_missing = generate_report_pdf(
            title=f"No Encontrados — {today}",
            columns=missing_report_cols,
            rows=missing_rows_dl,
            summary=missing_summary,
        )
        st.download_button(
            label="📥 Descargar solo no encontrados (PDF)",
            data=pdf_missing,
            file_name=f"no_encontrados_{today}.pdf",
            mime="application/pdf",
            key=f"{source}_dl_missing",
        )

    # Páginas para imprimir (solo KuDE)
    if source == "kude":
        kude_print_data = st.session_state.get("_kude_data", [])
        if kude_print_data and missing:
            st.divider()
            st.subheader("Páginas para imprimir")
            missing_set = set(missing)
            print_rows = []
            for page_num, kd in enumerate(kude_print_data, start=1):
                ns = kd.get("numero_simple", "")
                if ns in missing_set:
                    print_rows.append({
                        "Página": page_num,
                        "Nro. Factura": kd.get("numero_factura", "—"),
                        "Proveedor": kd.get("proveedor", "—"),
                        "Monto (Gs.)": _fmt_gs(kd["monto_total"]) if kd.get("monto_total") else "—",
                    })

            if print_rows:
                page_numbers = [str(r["Página"]) for r in print_rows]
                pcol1, pcol2 = st.columns([3, 2])
                with pcol1:
                    st.metric("Facturas faltantes a imprimir", len(print_rows))
                    st.dataframe(pd.DataFrame(print_rows), use_container_width=True, hide_index=True)
                with pcol2:
                    st.markdown("**Copiá esto en el campo de páginas de Edge / Chrome:**")
                    st.code(",".join(page_numbers))
                    st.caption("Archivo → Imprimir → Más opciones → Páginas personalizadas")
        elif not missing:
            st.divider()
            st.info("Todas las facturas ya están registradas. No hay páginas para imprimir.")


# == Paso 1: Entrada de datos ==================================================
st.subheader("1. Datos de entrada")
tab_kude, tab_pdf, tab_text, tab_excel = st.tabs(
    ["🧾 Factura Electrónica", "📄 Archivo", "✏️ Lista de valores", "📊 Excel / CSV"]
)

# -- KuDE ---------------------------------------------------------------------
with tab_kude:
    st.info(
        "Subí uno o varios archivos KuDE (el PDF que emite el proveedor "
        "al facturar electrónicamente en el sistema SIFEN)."
    )
    kude_gen = st.session_state.get("_kude_gen", 0)
    uploaded_kudes = st.file_uploader(
        "Subir KuDE(s)", type=["pdf"], accept_multiple_files=True,
        key=f"kude_upload_{kude_gen}",
    )

    if uploaded_kudes:
        file_ids = "_".join(f"{f.name}_{f.size}" for f in uploaded_kudes)
        cache_key = f"kude_{file_ids}"
        if st.session_state.get("_kude_cache_key") != cache_key:
            kude_data, kude_errors = extract_multiple_kudes(uploaded_kudes)
            st.session_state["_kude_data"] = kude_data
            st.session_state["_kude_errors"] = kude_errors
            st.session_state["_kude_cache_key"] = cache_key

        kude_data = st.session_state.get("_kude_data", [])
        kude_errors = st.session_state.get("_kude_errors", [])

        for fname in kude_errors:
            st.warning(f"No se pudo leer **{fname}** como KuDE.")

        if kude_data:
            st.success(f"**{len(kude_data)}** facturas electrónicas detectadas.")
            preview = [{
                "Archivo": k.get("archivo", ""),
                "Nro. Factura": k.get("numero_factura", "—"),
                "Proveedor": k.get("proveedor", "—"),
                "Fecha": str(k["fecha"]) if k.get("fecha") else "—",
                "Monto Total (Gs.)": _fmt_gs(k["monto_total"]) if k.get("monto_total") else "—",
            } for k in kude_data]
            st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)

            bcol1, bcol2 = st.columns(2)
            with bcol1:
                if st.button("📥 Cargar", key="kude_load_btn", use_container_width=True):
                    vals = [k["numero_simple"] for k in kude_data if k.get("numero_simple")]
                    _activate_source("kude", vals)
                    st.rerun()
            with bcol2:
                if st.button("🗑️ Limpiar", key="kude_clear_btn", use_container_width=True):
                    for k in ("_kude_data", "_kude_errors", "_kude_cache_key"):
                        st.session_state.pop(k, None)
                    _deactivate_source("kude")
                    st.session_state["_kude_gen"] = kude_gen + 1
                    st.rerun()

    if st.session_state.get("_active_source") == "kude":
        vals = st.session_state.get("_input_values", [])
        if vals:
            st.info(f"**{len(vals)}** valores listos para verificar.")
            with st.expander("Ver valores cargados"):
                st.dataframe(pd.DataFrame({"Valor": vals}), use_container_width=True, hide_index=True)

    _render_workflow("kude")

# -- PDF ----------------------------------------------------------------------
with tab_pdf:
    pdf_gen = st.session_state.get("_pdf_gen", 0)
    uploaded_pdf = st.file_uploader(
        "Subir PDF", type=["pdf"], key=f"pdf_upload_{pdf_gen}",
        help="El PDF debe contener tablas con encabezados.",
    )

    if uploaded_pdf is not None:
        file_id = f"pdf_{uploaded_pdf.name}_{uploaded_pdf.size}"
        if st.session_state.get("_pdf_cache_key") != file_id:
            try:
                cols_detected = extract_pdf_columns(uploaded_pdf)
                st.session_state["_pdf_columns"] = cols_detected
                st.session_state["_pdf_cache_key"] = file_id
            except Exception as exc:
                st.error(f"No se pudo leer el PDF: {exc}")
                st.stop()

        pdf_cols = st.session_state.get("_pdf_columns", [])
        if pdf_cols:
            selected_col = st.selectbox(
                "Columna a extraer del PDF", pdf_cols, key="pdf_col_select",
            )

            bcol1, bcol2 = st.columns(2)
            with bcol1:
                if st.button("📥 Cargar", key="pdf_load_btn", use_container_width=True):
                    try:
                        uploaded_pdf.seek(0)
                        vals = extract_column_from_pdf(uploaded_pdf, selected_col)
                        _activate_source("pdf", vals)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(f"Error al extraer columna: {exc}")
            with bcol2:
                if st.button("🗑️ Limpiar", key="pdf_clear_btn", use_container_width=True):
                    for k in ("_pdf_columns", "_pdf_cache_key"):
                        st.session_state.pop(k, None)
                    _deactivate_source("pdf")
                    st.session_state["_pdf_gen"] = pdf_gen + 1
                    st.rerun()
        else:
            st.warning("No se encontraron tablas con encabezados en el PDF.")

    if st.session_state.get("_active_source") == "pdf":
        vals = st.session_state.get("_input_values", [])
        if vals:
            st.info(f"**{len(vals)}** valores listos para verificar.")
            with st.expander("Ver valores cargados"):
                st.dataframe(pd.DataFrame({"Valor": vals}), use_container_width=True, hide_index=True)

    _render_workflow("pdf")

# -- Lista de valores ---------------------------------------------------------
with tab_text:
    text_gen = st.session_state.get("_text_gen", 0)
    text_input = st.text_area(
        "Ingresá valores separados por coma",
        height=200,
        placeholder="86285, 90648, 121241",
        key=f"manual_text_{text_gen}",
    )

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        if st.button("📥 Cargar", key="text_load_btn", use_container_width=True):
            if text_input.strip():
                raw = text_input.replace("\n", ",")
                lines = [l.strip() for l in raw.split(",") if l.strip()]
                if lines:
                    _activate_source("text", lines)
                    st.rerun()
                else:
                    st.warning("No se encontraron valores.")
            else:
                st.warning("Ingresá al menos un valor.")
    with bcol2:
        if st.button("🗑️ Limpiar", key="text_clear_btn", use_container_width=True):
            _deactivate_source("text")
            st.session_state["_text_gen"] = text_gen + 1
            st.rerun()

    if st.session_state.get("_active_source") == "text":
        vals = st.session_state.get("_input_values", [])
        if vals:
            st.info(f"**{len(vals)}** valores listos para verificar.")
            with st.expander("Ver valores cargados"):
                st.dataframe(pd.DataFrame({"Valor": vals}), use_container_width=True, hide_index=True)

    _render_workflow("text")

# -- Excel / CSV --------------------------------------------------------------
with tab_excel:
    excel_gen = st.session_state.get("_excel_gen", 0)
    uploaded_excel = st.file_uploader(
        "Subir Excel o CSV", type=["xlsx", "xls", "csv"],
        key=f"excel_upload_{excel_gen}",
    )

    if uploaded_excel is not None:
        file_id = f"excel_{uploaded_excel.name}_{uploaded_excel.size}"
        if st.session_state.get("_excel_cache_key") != file_id:
            try:
                if uploaded_excel.name.endswith(".csv"):
                    df_input = pd.read_csv(uploaded_excel)
                else:
                    df_input = pd.read_excel(uploaded_excel)
                st.session_state["_excel_columns"] = list(df_input.columns)
                st.session_state["_excel_df"] = df_input
                st.session_state["_excel_cache_key"] = file_id
            except Exception as exc:
                st.error(f"No se pudo leer el archivo: {exc}")

        excel_cols = st.session_state.get("_excel_columns", [])
        if excel_cols:
            sel_col = st.selectbox(
                "Columna a extraer", excel_cols, key="excel_col_select",
            )

            bcol1, bcol2 = st.columns(2)
            with bcol1:
                if st.button("📥 Cargar", key="excel_load_btn", use_container_width=True):
                    df_ex = st.session_state.get("_excel_df")
                    if df_ex is not None and sel_col:
                        vals = [
                            str(v).strip()
                            for v in df_ex[sel_col].dropna().tolist()
                            if str(v).strip()
                        ]
                        _activate_source("excel", vals)
                        st.rerun()
            with bcol2:
                if st.button("🗑️ Limpiar", key="excel_clear_btn", use_container_width=True):
                    for k in ("_excel_columns", "_excel_df", "_excel_cache_key"):
                        st.session_state.pop(k, None)
                    _deactivate_source("excel")
                    st.session_state["_excel_gen"] = excel_gen + 1
                    st.rerun()

    if st.session_state.get("_active_source") == "excel":
        vals = st.session_state.get("_input_values", [])
        if vals:
            st.info(f"**{len(vals)}** valores listos para verificar.")
            with st.expander("Ver valores cargados"):
                st.dataframe(pd.DataFrame({"Valor": vals}), use_container_width=True, hide_index=True)

    _render_workflow("excel")
