"""Reporte de Obra — resumen general + detalle de materiales y mano de obra.

Flujo:
1. El usuario filtra por Estado → Categoría → Obra.
2. Opcionalmente filtra por rango de fechas y rubros.
3. Presiona "Generar Reporte" para procesar los datos.
4. Se muestra un preview en pantalla (resumen + detalles).
5. Se ofrece descarga en PDF y botón de imprimir.
"""

import base64
from collections import defaultdict
from datetime import datetime, date

import streamlit as st
import streamlit.components.v1 as components

from connectors.supabase_connector import get_all_records
from core.base_tool import ToolMetadata
from generators.pdf_generator import generate_obra_report_pdf

TOOL = ToolMetadata(
    name="Reporte de Obra",
    description="Generá el reporte completo de una obra: resumen, materiales y mano de obra.",
    icon="📋",
    page_file="04_reporte_obra.py",
)


# ── CSS ───────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Reporte de Obra", layout="wide")

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
.js-sub { color: var(--js-muted); font-size: .875rem; margin-top: -10px; margin-bottom: 24px; }

/* Preview table styles */
.rpt-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.rpt-table th { background: #2e4053; color: white; padding: 6px 10px; text-align: left; }
.rpt-table th.right { text-align: right; }
.rpt-table td { padding: 5px 10px; border-bottom: 1px solid var(--js-border); }
.rpt-table td.right { text-align: right; font-variant-numeric: tabular-nums; }
.rpt-row-obra   { background: #1a252f; color: white; font-weight: 700; }
.rpt-row-sector { background: #2e4053; color: white; font-weight: 700; }
.rpt-row-rubro  { background: #5d6d7e; color: white; font-weight: 700; }
.rpt-row-total  { background: #aab7b8; font-weight: 700; }
.rpt-row-sub    { background: #d5d8dc; font-weight: 600; }
.rpt-row-alt    { background: rgba(255,255,255,0.03); }
.rpt-row-trab   { background: rgba(255,255,255,0.06); font-weight: 600; }
.rpt-row-spacer { height: 10px; background: transparent; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _fmt_gs(value) -> str:
    try:
        return f"Gs. {int(float(value)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "---"


def _fmt_date(val) -> str:
    if not val:
        return "—"
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(val)


def _in_range(fecha_str: str, desde, hasta) -> bool:
    """True si la fecha está dentro del rango (None = sin límite)."""
    if not fecha_str:
        return True
    try:
        d = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return True
    if desde and d < desde:
        return False
    if hasta and d > hasta:
        return False
    return True


# ── Data loading ──────────────────────────────────────────────────────────────
def _load_maps():
    """Carga dimensiones para resolución de IDs."""
    clientes_recs = get_all_records("dim_cliente")
    sectores_recs = get_all_records("dim_sector")
    rubros_recs   = get_all_records("dim_rubro")
    trab_recs     = get_all_records("dim_trabajador")
    return {
        "clientes":     {r["id"]: r.get("nombre_cliente", str(r["id"])) for r in clientes_recs},
        "sectores":     {r["id"]: r.get("nombre_sector",  str(r["id"])) for r in sectores_recs},
        "rubros":       {r["id"]: r.get("rubro",          str(r["id"])) for r in rubros_recs},
        "trabajadores": {r["id"]: r.get("nombre_completo",str(r["id"])) for r in trab_recs},
    }


# ── Procesamiento ─────────────────────────────────────────────────────────────
def _enrich_compras(compras_raw, maps, obra_sel_id, rubros_sel, desde, hasta):
    """Filtra y enriquece registros de fact_compra para la obra seleccionada."""
    result = []
    for row in compras_raw:
        if row.get("obra_id") != obra_sel_id:
            continue
        fecha = row.get("fecha", "") or ""
        if not _in_range(fecha, desde, hasta):
            continue
        rubro = maps["rubros"].get(row.get("rubro_id"), "SIN RUBRO")
        if rubros_sel and rubro not in rubros_sel:
            continue
        result.append({
            **row,
            "_sector": maps["sectores"].get(row.get("sector_id"), "SIN SECTOR"),
            "_rubro":  rubro,
        })
    return result


def _enrich_pagos(pagos_raw, maps, obra_sel_id, rubros_sel, desde, hasta):
    """Filtra y enriquece registros de fact_pago para la obra seleccionada."""
    result = []
    for row in pagos_raw:
        if row.get("obra_id") != obra_sel_id:
            continue
        fecha = row.get("fecha_pago", "") or ""
        if not _in_range(fecha, desde, hasta):
            continue
        rubro = maps["rubros"].get(row.get("rubro_id"), "SIN RUBRO")
        if rubros_sel and rubro not in rubros_sel:
            continue
        result.append({
            **row,
            "_sector":     maps["sectores"].get(row.get("sector_id"), "SIN SECTOR"),
            "_rubro":      rubro,
            "_trabajador": maps["trabajadores"].get(row.get("trabajador_id"), "SIN NOMBRE"),
        })
    return result


def _build_resumen(compras, pagos, obra_clave):
    """Construye {obra: {sector: {rubro: {mat, mo}}}}."""
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"mat": 0.0, "mo": 0.0})))
    for row in compras:
        sec = row["_sector"]
        rub = row["_rubro"]
        data[obra_clave][sec][rub]["mat"] += float(row.get("monto_total", 0) or 0)
    for row in pagos:
        sec = row["_sector"]
        rub = row["_rubro"]
        data[obra_clave][sec][rub]["mo"] += float(row.get("monto_pago", 0) or 0)
    # Convert defaultdicts to plain dicts
    return {
        obra: {
            sec: {rub: vals for rub, vals in rubros.items()}
            for sec, rubros in sectores.items()
        }
        for obra, sectores in data.items()
    }


# ── Preview HTML ──────────────────────────────────────────────────────────────
def _resumen_html(resumen: dict, obra_clave: str) -> str:
    obra_data = resumen.get(obra_clave, {})
    rows = []
    rows.append(
        '<table class="rpt-table">'
        '<thead><tr>'
        '<th>Obra / Sector / Rubro</th>'
        '<th class="right">Materiales</th>'
        '<th class="right">Mano de Obra</th>'
        '<th class="right">MAT + MO</th>'
        '</tr></thead><tbody>'
    )
    rows.append(f'<tr class="rpt-row-obra"><td colspan="4">{obra_clave}</td></tr>')

    total_mat = total_mo = 0.0
    for sector in sorted(obra_data, key=lambda s: -sum(v["mat"]+v["mo"] for v in obra_data[s].values())):
        rows.append(f'<tr class="rpt-row-sector"><td colspan="4">&nbsp;&nbsp;{sector}</td></tr>')
        for rubro, vals in sorted(obra_data[sector].items(), key=lambda x: -(x[1]["mat"]+x[1]["mo"])):
            mat = vals["mat"]
            mo  = vals["mo"]
            total_mat += mat
            total_mo  += mo
            mat_txt = _fmt_gs(mat) if mat else "---"
            mo_txt  = _fmt_gs(mo)  if mo  else "---"
            rows.append(
                f'<tr class="rpt-row-rubro">'
                f'<td>&nbsp;&nbsp;&nbsp;&nbsp;{rubro}</td>'
                f'<td class="right">{mat_txt}</td>'
                f'<td class="right">{mo_txt}</td>'
                f'<td class="right">{_fmt_gs(mat+mo)}</td>'
                f'</tr>'
            )

    rows.append(
        f'<tr class="rpt-row-total">'
        f'<td>Total:</td>'
        f'<td class="right">{_fmt_gs(total_mat)}</td>'
        f'<td class="right">{_fmt_gs(total_mo)}</td>'
        f'<td class="right">{_fmt_gs(total_mat+total_mo)}</td>'
        f'</tr>'
    )
    rows.append("</tbody></table>")
    return "".join(rows)


def _aggregate_by_desc(items: list[dict]) -> list[dict]:
    """Suma cantidad y monto de ítems con la misma descripción."""
    agg: dict[str, dict] = {}
    for item in items:
        key = (item.get("descripcion", "") or "").strip().upper()
        if key in agg:
            agg[key]["monto_total"] = float(agg[key].get("monto_total", 0) or 0) + float(item.get("monto_total", 0) or 0)
            try:
                agg[key]["cantidad"] = float(agg[key].get("cantidad", 0) or 0) + float(item.get("cantidad", 0) or 0)
            except (ValueError, TypeError):
                pass
        else:
            agg[key] = dict(item)
    return list(agg.values())


def _compras_html(compras: list[dict], obra_clave: str) -> str:
    by_sector = defaultdict(lambda: defaultdict(list))
    for row in compras:
        by_sector[row["_sector"]][row["_rubro"]].append(row)

    parts = ['<table class="rpt-table"><thead><tr>'
             '<th>Descripción</th><th>Unidad</th><th class="right">Cant.</th>'
             '<th class="right">Monto total</th></tr></thead><tbody>']

    parts.append(f'<tr class="rpt-row-obra"><td colspan="4">{obra_clave}</td></tr>')

    for sector in sorted(by_sector, key=lambda s: -sum(float(it.get("monto_total",0) or 0) for items in by_sector[s].values() for it in items)):
        parts.append(f'<tr class="rpt-row-sector"><td colspan="4">&nbsp;&nbsp;{sector}</td></tr>')
        sector_total = 0.0
        for rubro_idx, (rubro, items_raw) in enumerate(sorted(by_sector[sector].items(), key=lambda x: -sum(float(it.get("monto_total",0) or 0) for it in x[1]))):
            items = sorted(_aggregate_by_desc(items_raw), key=lambda x: -float(x.get("monto_total",0) or 0))
            if rubro_idx > 0:
                parts.append('<tr class="rpt-row-spacer"><td colspan="4"></td></tr>')
            parts.append(f'<tr class="rpt-row-rubro"><td colspan="4">&nbsp;&nbsp;&nbsp;&nbsp;{rubro}</td></tr>')
            rubro_total = 0.0
            for i, item in enumerate(items):
                monto = float(item.get("monto_total", 0) or 0)
                rubro_total += monto
                cant = item.get("cantidad", "")
                try:
                    cant_txt = str(int(float(cant))) if cant and str(cant).strip() else "---"
                except (ValueError, TypeError):
                    cant_txt = "---"
                cls = "rpt-row-alt" if i % 2 else ""
                parts.append(
                    f'<tr class="{cls}">'
                    f'<td>{item.get("descripcion","")}</td>'
                    f'<td>{item.get("unidad","GL")}</td>'
                    f'<td class="right">{cant_txt}</td>'
                    f'<td class="right">{_fmt_gs(monto)}</td>'
                    f'</tr>'
                )
            parts.append(
                f'<tr class="rpt-row-sub">'
                f'<td>&nbsp;&nbsp;&nbsp;&nbsp;{rubro} Total</td>'
                f'<td></td><td class="right">---</td>'
                f'<td class="right">{_fmt_gs(rubro_total)}</td>'
                f'</tr>'
            )
            sector_total += rubro_total
        parts.append(
            f'<tr class="rpt-row-total">'
            f'<td>Total:</td>'
            f'<td></td><td></td>'
            f'<td class="right">{_fmt_gs(sector_total)}</td>'
            f'</tr>'
        )

    parts.append("</tbody></table>")
    return "".join(parts)


def _pagos_html(pagos: list[dict], obra_clave: str, *, show_detail: bool = True) -> str:
    by_sector = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in pagos:
        by_sector[row["_sector"]][row["_rubro"]][row["_trabajador"]].append(row)

    parts = ['<table class="rpt-table"><thead><tr>'
             '<th>Trabajador / Fecha</th><th>Concepto</th><th>Método</th>'
             '<th class="right">Monto Pago</th></tr></thead><tbody>']

    parts.append(f'<tr class="rpt-row-obra"><td colspan="4">{obra_clave}</td></tr>')

    def _trab_total(items): return sum(float(r.get("monto_pago",0) or 0) for r in items)
    def _rubro_total(trabas): return sum(_trab_total(it) for it in trabas.values())
    def _sector_total(rubros): return sum(_rubro_total(tr) for tr in rubros.values())

    sector_grand = 0.0
    for sector in sorted(by_sector, key=lambda s: -_sector_total(by_sector[s])):
        parts.append(f'<tr class="rpt-row-sector"><td colspan="4">&nbsp;&nbsp;{sector}</td></tr>')
        for rubro_idx, (rubro, trabas) in enumerate(sorted(by_sector[sector].items(), key=lambda x: -_rubro_total(x[1]))):
            if rubro_idx > 0:
                parts.append('<tr class="rpt-row-spacer"><td colspan="4"></td></tr>')
            parts.append(f'<tr class="rpt-row-rubro"><td colspan="4">&nbsp;&nbsp;&nbsp;&nbsp;{rubro}</td></tr>')
            rubro_total = 0.0
            for trab, items in sorted(trabas.items(), key=lambda x: -_trab_total(x[1])):
                trab_total = sum(float(r.get("monto_pago", 0) or 0) for r in items)
                rubro_total += trab_total
                # Fila de trabajador: siempre visible
                parts.append(
                    f'<tr class="rpt-row-trab">'
                    f'<td colspan="3">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{trab}</td>'
                    f'<td class="right">{_fmt_gs(trab_total)}</td>'
                    f'</tr>'
                )
                # Filas de detalle: sólo si show_detail=True
                if show_detail:
                    for i, r in enumerate(sorted(items, key=lambda r: -float(r.get("monto_pago",0) or 0))):
                        cls = "rpt-row-alt" if i % 2 else ""
                        parts.append(
                            f'<tr class="{cls}">'
                            f'<td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{_fmt_date(r.get("fecha_pago"))}</td>'
                            f'<td>{r.get("concepto","")}</td>'
                            f'<td>{r.get("metodo_pago","")}</td>'
                            f'<td class="right">{_fmt_gs(r.get("monto_pago",0))}</td>'
                            f'</tr>'
                        )
            sector_grand += rubro_total
            parts.append(
                f'<tr class="rpt-row-sub">'
                f'<td>&nbsp;&nbsp;&nbsp;&nbsp;{rubro} Total</td>'
                f'<td colspan="2"></td>'
                f'<td class="right">{_fmt_gs(rubro_total)}</td>'
                f'</tr>'
            )

    parts.append(
        f'<tr class="rpt-row-total">'
        f'<td>Total:</td><td colspan="2"></td>'
        f'<td class="right">{_fmt_gs(sector_grand)}</td>'
        f'</tr>'
    )
    parts.append("</tbody></table>")
    return "".join(parts)


# ── Print helper ──────────────────────────────────────────────────────────────
def _render_print_button(pdf_bytes: bytes):
    b64 = base64.b64encode(pdf_bytes).decode()
    components.html(f"""
    <style>
    #js-print-btn {{
        background-color: #E8622A; color: white; border: none;
        padding: 8px 20px; border-radius: 6px; cursor: pointer;
        font-size: 14px; font-weight: 600;
    }}
    #js-print-btn:hover {{ background-color: #cf5524; }}
    </style>
    <button id="js-print-btn">🖨️ Imprimir</button>
    <script>
    (function() {{
        const b64 = "{b64}";
        document.getElementById("js-print-btn").addEventListener("click", function() {{
            const byteChars = atob(b64);
            const byteArr = new Uint8Array(byteChars.length);
            for (let i = 0; i < byteChars.length; i++) byteArr[i] = byteChars.charCodeAt(i);
            const blob = new Blob([byteArr], {{type: "application/pdf"}});
            const url  = URL.createObjectURL(blob);
            const win  = window.open(url);
            if (win) win.print();
        }});
    }})();
    </script>
    """, height=50)


# ── UI principal ──────────────────────────────────────────────────────────────
st.title("📋 Reporte de Obra")
st.markdown('<p class="js-sub">Resumen general de materiales y mano de obra por obra.</p>', unsafe_allow_html=True)

# Cargar datos base (siempre, para los filtros)
try:
    with st.spinner("Cargando datos..."):
        obras_raw = get_all_records("dim_obra")
        maps = _load_maps()
except ConnectionError as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    st.stop()

# Construir opciones para filtros cascading
estados = sorted({row.get("estado_obra", "") for row in obras_raw if row.get("estado_obra")})

with st.expander("🔎 Filtros", expanded=True):
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        estado_sel = st.selectbox("Estado de obra", ["Todos"] + estados, key="rpt_estado")

    obras_por_estado = [
        r for r in obras_raw
        if estado_sel == "Todos" or r.get("estado_obra") == estado_sel
    ]
    cats_disponibles = sorted({r.get("categoria_obra", "") for r in obras_por_estado if r.get("categoria_obra")})

    with col2:
        cat_sel = st.selectbox("Categoría", ["Todas"] + cats_disponibles, key="rpt_cat")

    obras_filtradas = [
        r for r in obras_por_estado
        if cat_sel == "Todas" or r.get("categoria_obra") == cat_sel
    ]
    obra_opts = sorted([r.get("clave") or r.get("nombre", str(r["id"])) for r in obras_filtradas])

    with col3:
        obra_sel = st.selectbox("Obra", obra_opts if obra_opts else ["Sin obras"], key="rpt_obra")

    st.divider()

    col_d1, col_d2, col_rb = st.columns([1, 1, 2])
    with col_d1:
        fecha_desde = st.date_input("Fecha desde", value=None, key="rpt_desde")
    with col_d2:
        fecha_hasta = st.date_input("Fecha hasta", value=None, key="rpt_hasta")

    all_rubros = sorted(maps["rubros"].values())
    with col_rb:
        rubros_sel = st.multiselect(
            "Rubros (vacío = todos)",
            options=all_rubros,
            default=[],
            key="rpt_rubros",
        )

generar = st.button("📥 Generar Reporte", type="primary", key="rpt_generar")

if generar and obra_opts and obra_sel != "Sin obras":
    # Cargar transaccionales
    with st.spinner("Procesando datos..."):
        compras_raw = get_all_records("fact_compra")
        pagos_raw   = get_all_records("fact_pago")

    # Resolver el ID entero de la obra seleccionada
    obra_record = next(
        (r for r in obras_raw if (r.get("clave") or r.get("nombre", "")) == obra_sel),
        {},
    )
    obra_sel_id = obra_record.get("id")
    cliente_id = obra_record.get("cliente_id")
    cliente_nombre = maps["clientes"].get(cliente_id, "—") if cliente_id else "—"

    rubros_filter = set(rubros_sel) if rubros_sel else None

    compras = _enrich_compras(
        compras_raw, maps, obra_sel_id,
        rubros_filter,
        fecha_desde, fecha_hasta,
    )
    pagos = _enrich_pagos(
        pagos_raw, maps, obra_sel_id,
        rubros_filter,
        fecha_desde, fecha_hasta,
    )

    if not compras and not pagos:
        st.warning("No se encontraron registros para los filtros seleccionados.")
        st.stop()

    resumen = _build_resumen(compras, pagos, obra_sel)
    hoy = date.today()
    fecha_gen = f"{hoy.day}/{hoy.month}/{hoy.year}"

    st.session_state["rpt_04_data"] = {
        "obra_sel": obra_sel,
        "cliente_nombre": cliente_nombre,
        "fecha_gen": fecha_gen,
        "resumen": resumen,
        "compras": compras,
        "pagos": pagos,
    }

# ── Render preview y exportes ─────────────────────────────────────────────────
if "rpt_04_data" in st.session_state:
    d = st.session_state["rpt_04_data"]
    obra_sel       = d["obra_sel"]
    cliente_nombre = d["cliente_nombre"]
    fecha_gen      = d["fecha_gen"]
    resumen        = d["resumen"]
    compras        = d["compras"]
    pagos          = d["pagos"]

    st.divider()
    st.caption(f"Cliente: **{cliente_nombre}** | Obra: **{obra_sel}** | Generado: {fecha_gen}")

    # Preview
    tab1, tab2, tab3 = st.tabs(["📊 Resumen General", "🧱 Materiales", "👷 Mano de Obra"])

    with tab1:
        st.markdown(_resumen_html(resumen, obra_sel), unsafe_allow_html=True)

    with tab2:
        if compras:
            st.markdown(_compras_html(compras, obra_sel), unsafe_allow_html=True)
        else:
            st.info("Sin registros de materiales para los filtros aplicados.")

    with tab3:
        if pagos:
            show_detail = st.toggle("Ver detalle por pago", value=False, key="rpt_mo_detail")
            st.markdown(_pagos_html(pagos, obra_sel, show_detail=show_detail), unsafe_allow_html=True)
        else:
            st.info("Sin registros de mano de obra para los filtros aplicados.")

    st.divider()

    # Generar PDF (respeta el estado del toggle de MO)
    mo_detail = st.session_state.get("rpt_mo_detail", False)
    with st.spinner("Preparando PDF..."):
        pdf_bytes = generate_obra_report_pdf(
            obra_nombre=obra_sel,
            cliente_nombre=cliente_nombre,
            fecha_generacion=fecha_gen,
            resumen=resumen,
            compras=compras,
            pagos=pagos,
            show_mo_detail=mo_detail,
        )

    col_dl, col_pr, _ = st.columns([1, 1, 4])
    with col_dl:
        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_bytes,
            file_name=f"Reporte Obra - {obra_sel}.pdf",
            mime="application/pdf",
            key="rpt_download",
        )
    with col_pr:
        _render_print_button(pdf_bytes)
