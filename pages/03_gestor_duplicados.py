"""Gestor de Duplicados — detecta y permite eliminar registros duplicados en FactCompra.

Lógica de detección:
- Una "entrada" = todos los registros con el mismo (NumeroDocumento normalizado,
  ProveedorTexto, FechaCompra). Una factura puede tener N líneas (una por artículo).
- Se detecta un duplicado cuando dos entradas comparten (NumDoc, Proveedor) y
  sus totales sumados coinciden.
- El original es la entrada con la fecha de creación más antigua; el resto son duplicados.
"""

import re
from collections import defaultdict
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from streamlit_sortables import sort_items
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from connectors.airtable import delete_record as at_delete_record
from connectors.airtable import get_all_records as at_get_all_records
from connectors.supabase_connector import (
    clear_cache,
    create_record,
    delete_record,
    get_all_records,
)
from core.base_tool import ToolMetadata

TOOL = ToolMetadata(
    name="Gestor de Duplicados",
    description="Detectá y eliminá facturas duplicadas en FactCompra.",
    icon="🔍",
    page_file="03_gestor_duplicados.py",
)

_ALL_COLS = [
    {"key": "compra_nro",        "label": "N° Compra"},
    {"key": "obra_id",           "label": "Obra"},
    {"key": "_proveedor",        "label": "Proveedor"},
    {"key": "fecha",             "label": "Fecha Compra"},
    {"key": "nro_factura",       "label": "N° Documento"},
    {"key": "descripcion",       "label": "Descripción"},
    {"key": "cantidad",          "label": "Cantidad"},
    {"key": "unidad",            "label": "Unidad"},
    {"key": "monto_total",       "label": "Monto (Gs.)"},
    {"key": "tipo_documento",    "label": "Tipo Doc."},
    {"key": "observaciones",     "label": "Observaciones"},
    {"key": "created_at_source", "label": "Fecha de creación"},
]

_DEFAULT_KEYS = [
    "obra_id", "_proveedor", "fecha", "nro_factura",
    "descripcion", "cantidad", "monto_total", "created_at_source",
]

_KEY_TO_LABEL = {c["key"]: c["label"] for c in _ALL_COLS}


# -- FalsosDuplicados ---------------------------------------------------------

def _group_key(group: dict) -> str:
    if group["type"] == "invoice":
        return f"inv:{group['nro_doc_norm']}:{group['proveedor_raw']}:{round(group['total'], 2)}"
    return f"line:{group['nro_doc_norm']}:{group['proveedor_raw']}:{group['fecha_compra']}:{round(group['total'], 2)}"


def _load_dismissed_keys() -> set[str]:
    try:
        recs = get_all_records("aux_falsos_duplicados", columns="clave_grupo")
        return {r.get("clave_grupo", "") for r in recs if r.get("clave_grupo")}
    except Exception:
        return set()


def _dismiss_group(group: dict, prov_name: str) -> None:
    create_record("aux_falsos_duplicados", {
        "clave_grupo": _group_key(group),
        "tipo":        "Factura" if group["type"] == "invoice" else "Línea",
        "nro_factura": group["nro_doc_norm"],
        "proveedor":   prov_name,
    })


# -- Helpers ------------------------------------------------------------------

def _normalize_nro_doc(raw: str) -> str:
    if not raw:
        return ""
    raw = str(raw).strip()
    parts = [p.strip() for p in re.split(r"[-–]", raw) if p.strip()]
    if len(parts) == 3:
        try:
            return f"{parts[0].zfill(3)}-{parts[1].zfill(3)}-{parts[2].zfill(7)}"
        except Exception:
            pass
    digits = re.sub(r"\D", "", raw)
    return digits.zfill(7) if digits else raw.lower()


def _parse_created(val) -> datetime:
    if not val:
        return datetime.min
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f+00:00", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(val)[:26], fmt)
        except ValueError:
            continue
    return datetime.min


def _fmt_gs(value) -> str:
    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(value) if value else "—"


def _resolve_obra(val, nm_obra: dict) -> str:
    if val is None:
        return "—"
    return nm_obra.get(int(val), str(val)) if val else "—"


def _detect_duplicates(records: list[dict]) -> list[dict]:
    entry_map: dict[tuple, list[dict]] = defaultdict(list)
    for rec in records:
        nro_norm = _normalize_nro_doc(str(rec.get("nro_factura", "") or ""))
        if not nro_norm:
            continue
        prov  = str(rec.get("proveedor_texto", "") or "")
        fecha = str(rec.get("fecha", "") or "")
        entry_map[(nro_norm, prov, fecha)].append(rec)

    invoice_map: dict[tuple, list[dict]] = defaultdict(list)
    for (nro_norm, prov, fecha), recs in entry_map.items():
        total = sum(float(r.get("monto_total", 0) or 0) for r in recs)
        min_created = min(
            (_parse_created(r.get("created_at_source")) for r in recs),
            default=datetime.min,
        )
        invoice_map[(nro_norm, prov)].append({
            "fecha_compra": fecha,
            "total": total,
            "min_created": min_created,
            "records": recs,
        })

    result = []
    for (nro_norm, prov), entry_list in invoice_map.items():
        if len(entry_list) < 2:
            continue
        by_total: dict[float, list] = defaultdict(list)
        for entry in entry_list:
            by_total[round(entry["total"], 2)].append(entry)
        for total, matching in by_total.items():
            if len(matching) < 2:
                continue
            sorted_entries = sorted(matching, key=lambda e: e["min_created"])
            result.append({
                "type": "invoice",
                "nro_doc_norm": nro_norm,
                "proveedor_raw": prov,
                "total": total,
                "entries": sorted_entries,
            })
    return result


def _detect_line_duplicates(records: list[dict]) -> list[dict]:
    entry_map: dict[tuple, list[dict]] = defaultdict(list)
    for rec in records:
        nro_norm = _normalize_nro_doc(str(rec.get("nro_factura", "") or ""))
        if not nro_norm:
            continue
        prov  = str(rec.get("proveedor_texto", "") or "")
        fecha = str(rec.get("fecha", "") or "")
        entry_map[(nro_norm, prov, fecha)].append(rec)

    result = []
    for (nro_norm, prov, fecha), recs in entry_map.items():
        line_map: dict[float, list[dict]] = defaultdict(list)
        for rec in recs:
            monto = round(float(rec.get("monto_total", 0) or 0), 2)
            if monto:
                line_map[monto].append(rec)

        for monto, line_recs in line_map.items():
            if len(line_recs) < 2:
                continue
            sorted_recs = sorted(line_recs, key=lambda r: _parse_created(r.get("created_at_source")))
            entries = [
                {
                    "fecha_compra": fecha,
                    "total": monto,
                    "min_created": _parse_created(r.get("created_at_source")),
                    "records": [r],
                }
                for r in sorted_recs
            ]
            result.append({
                "type": "line",
                "nro_doc_norm": nro_norm,
                "proveedor_raw": prov,
                "fecha_compra": fecha,
                "total": monto,
                "entries": entries,
            })
    return result


def _build_df(
    records: list[dict],
    selected_keys: list[str],
    nm_obra: dict,
    include_delete_col: bool = False,
) -> pd.DataFrame:
    rows = []
    for r in records:
        row: dict = {}
        if include_delete_col:
            row["Eliminar"] = True
        for key in selected_keys:
            if key == "_proveedor":
                row[key] = r.get("_proveedor", "—")
            elif key == "obra_id":
                row[key] = _resolve_obra(r.get("obra_id"), nm_obra)
            elif key == "monto_total":
                row[key] = _fmt_gs(r.get("monto_total", ""))
            elif key == "created_at_source":
                raw = r.get("created_at_source", "")
                row[key] = str(raw)[:19].replace("T", " ") if raw else "—"
            else:
                val = r.get(key, "")
                row[key] = str(val) if val not in (None, "") else "—"
        rows.append(row)

    df = pd.DataFrame(rows)
    df.rename(
        columns={k: _KEY_TO_LABEL.get(k, k) for k in df.columns if k != "Eliminar"},
        inplace=True,
    )
    return df


# -- PDF ----------------------------------------------------------------------

def _generate_duplicates_pdf(dup_groups: list[dict], nm_obra: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=30*mm, rightMargin=20*mm, topMargin=25*mm, bottomMargin=25*mm,
    )

    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("JSTitle", parent=styles["Heading1"], fontSize=16,
                             fontName="Helvetica-Bold", textColor=colors.HexColor("#E8622A"), spaceAfter=4)
    s_sub   = ParagraphStyle("JSSub", parent=styles["Normal"], fontSize=8,
                             textColor=colors.HexColor("#7F8C8D"), spaceAfter=10)
    s_doc   = ParagraphStyle("JSDoc", parent=styles["Normal"], fontSize=10,
                             fontName="Helvetica-Bold", textColor=colors.HexColor("#2C3E50"),
                             spaceBefore=10, spaceAfter=4)
    s_cap   = ParagraphStyle("JSCap", parent=styles["Normal"], fontSize=8,
                             textColor=colors.HexColor("#7F8C8D"), spaceAfter=3)
    s_cell  = ParagraphStyle("JSCell", parent=styles["Normal"], fontSize=7.5)
    s_hdr   = ParagraphStyle("JSHdr", parent=styles["Normal"], fontSize=7.5,
                             fontName="Helvetica-Bold", textColor=colors.white)

    avail_w = A4[0] - 50 * mm
    c_accent = colors.HexColor("#E8622A")
    c_orig   = colors.HexColor("#D5F5E3")
    c_dup    = colors.HexColor("#FADBD8")
    c_line   = colors.HexColor("#FDEBD0")
    c_grid   = colors.HexColor("#CCCCCC")

    pdf_cols = [
        {"key": "estado",      "label": "Estado",       "w": 22},
        {"key": "nro_factura", "label": "N° Documento", "w": 30},
        {"key": "_proveedor",  "label": "Proveedor",    "w": 38},
        {"key": "fecha",       "label": "Fecha",        "w": 18},
        {"key": "descripcion", "label": "Descripción",  "w": 52},
        {"key": "cantidad",    "label": "Cant.",         "w": 10},
        {"key": "monto_total", "label": "Monto (Gs.)",  "w": 24},
    ]
    total_mm   = sum(c["w"] for c in pdf_cols)
    col_widths = [c["w"] / total_mm * avail_w for c in pdf_cols]

    story = [
        Paragraph("Reporte de Duplicados — FactCompra", s_title),
        Paragraph(
            f"JS Construcciones · {datetime.today().strftime('%d/%m/%Y %H:%M')} · "
            f"{len(dup_groups)} grupo(s) detectado(s)", s_sub,
        ),
        Spacer(1, 5*mm),
    ]

    inv_n  = sum(1 for g in dup_groups if g["type"] == "invoice")
    line_n = sum(1 for g in dup_groups if g["type"] == "line")
    risk_n = sum(sum(len(e["records"]) for e in g["entries"][1:]) for g in dup_groups)

    sum_data = [
        [Paragraph("<b>Tipo</b>", s_hdr),               Paragraph("<b>Cant.</b>", s_hdr)],
        [Paragraph("Duplicados de factura", s_cell),     Paragraph(str(inv_n),  s_cell)],
        [Paragraph("Líneas duplicadas",     s_cell),     Paragraph(str(line_n), s_cell)],
        [Paragraph("Registros en riesgo",   s_cell),     Paragraph(str(risk_n), s_cell)],
    ]
    sum_tbl = Table(sum_data, colWidths=[130*mm, 30*mm])
    sum_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), c_accent),
        ("BACKGROUND",    (0, 2), (-1, 2), colors.HexColor("#F5F5F5")),
        ("GRID",          (0, 0), (-1, -1), 0.5, c_grid),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("ALIGN",         (1, 0), (1, -1), "CENTER"),
    ]))
    story += [sum_tbl, Spacer(1, 8*mm)]

    doc_groups_pdf: dict[tuple, list[dict]] = {}
    for g in dup_groups:
        dk = (g["nro_doc_norm"], g["proveedor_raw"])
        doc_groups_pdf.setdefault(dk, []).append(g)

    for (nro, prov_raw), grp_list in doc_groups_pdf.items():
        story.append(Paragraph(f"{nro}  ·  {prov_raw}", s_doc))
        for grp in grp_list:
            is_line = grp["type"] == "line"
            story.append(Paragraph(
                f"{'Línea repetida' if is_line else 'Factura duplicada'} · "
                f"Gs. {_fmt_gs(grp['total'])}",
                s_cap,
            ))
            hdr_row = [Paragraph(f"<b>{c['label']}</b>", s_hdr) for c in pdf_cols]
            rows = [hdr_row]
            row_bgs = []
            for ei, entry in enumerate(grp["entries"]):
                if ei == 0:
                    estado, bg = "ORIGINAL",   c_orig
                elif is_line:
                    estado, bg = "LÍNEA DUP.", c_line
                else:
                    estado, bg = "DUPLICADO",  c_dup
                for rec in entry["records"]:
                    row = []
                    for col in pdf_cols:
                        k = col["key"]
                        if k == "estado":
                            row.append(Paragraph(f"<b>{estado}</b>", s_cell))
                        elif k == "_proveedor":
                            row.append(Paragraph(str(rec.get("_proveedor", "—")), s_cell))
                        elif k == "monto_total":
                            row.append(Paragraph(_fmt_gs(rec.get("monto_total", "")), s_cell))
                        elif k == "obra_id":
                            row.append(Paragraph(_resolve_obra(rec.get("obra_id"), nm_obra), s_cell))
                        else:
                            val = rec.get(k, "")
                            row.append(Paragraph(str(val) if val not in (None, "") else "—", s_cell))
                    rows.append(row)
                    row_bgs.append(bg)

            cmds = [
                ("BACKGROUND",    (0, 0), (-1, 0), c_accent),
                ("GRID",          (0, 0), (-1, -1), 0.4, c_grid),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 3),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
            ]
            for ri, bg in enumerate(row_bgs):
                cmds.append(("BACKGROUND", (0, ri+1), (-1, ri+1), bg))

            tbl = Table(rows, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(TableStyle(cmds))
            story += [tbl, Spacer(1, 3*mm)]
        story.append(Spacer(1, 4*mm))

    doc.build(story)
    return buf.getvalue()


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
.js-sub { color: var(--js-muted); font-size: .875rem; margin-top: -10px; margin-bottom: 24px; }
.js-grp-hdr {
    display: flex; justify-content: space-between; align-items: flex-start;
    padding-bottom: 12px; border-bottom: 1px solid var(--js-border); margin-bottom: 16px;
}
.js-grp-nro  { font-size: .95rem; font-weight: 700; font-family: monospace; letter-spacing: .4px; }
.js-grp-prov { font-size: .8rem; color: var(--js-muted); margin-top: 3px; }
.js-grp-tag  {
    font-size: .7rem; color: var(--js-muted); border: 1px solid var(--js-border);
    border-radius: 99px; padding: 3px 10px; white-space: nowrap; margin-top: 2px;
}
.js-pill {
    display: inline-block; border-radius: 3px; padding: 2px 8px;
    font-size: .68rem; font-weight: 700; letter-spacing: .8px;
    text-transform: uppercase; margin-bottom: 6px;
}
.js-orig { background: rgba(39,174,96,.12);  color: #27AE60; border: 1px solid rgba(39,174,96,.2); }
.js-dup  { background: rgba(231,76,60,.12);  color: #E74C3C; border: 1px solid rgba(231,76,60,.2); }
.js-line { background: rgba(230,126,34,.12); color: #E67E22; border: 1px solid rgba(230,126,34,.2); }
.js-cap  { font-size: .8rem; color: var(--js-muted); margin: 0 0 10px; }
</style>
""", unsafe_allow_html=True)

# -- Título -------------------------------------------------------------------

st.title("🔍 Gestor de Duplicados")
st.markdown('<p class="js-sub">FactCompra · Detectá y eliminá registros duplicados</p>', unsafe_allow_html=True)

# -- Feedback post-eliminación ------------------------------------------------

if st.session_state.get("_deleted_info"):
    info = st.session_state.pop("_deleted_info")
    if info.get("errors"):
        st.error(f"Error al eliminar: {'; '.join(info['errors'])}")
    else:
        st.success(f"✅ **{info['count']} registro(s) eliminado(s)** · {info['nro']} · {info['proveedor']}")

# -- Barra de acciones --------------------------------------------------------

_label_to_col   = {c["label"]: c for c in _ALL_COLS}
_default_labels = [c["label"] for c in _ALL_COLS if c["key"] in _DEFAULT_KEYS]

if "_col_order_03" not in st.session_state:
    st.session_state["_col_order_03"] = _default_labels.copy()

bar_col1, bar_col2 = st.columns([1, 4])
with bar_col1:
    with st.popover("⚙️ Columnas"):
        for _col in _ALL_COLS:
            _checked = _col["label"] in st.session_state["_col_order_03"]
            if st.checkbox(_col["label"], value=_checked, key=f"chk_03_{_col['key']}"):
                if not _checked:
                    st.session_state["_col_order_03"].append(_col["label"])
            else:
                if _checked:
                    st.session_state["_col_order_03"].remove(_col["label"])
with bar_col2:
    if st.button("🔍 Buscar duplicados", type="primary", use_container_width=True):
        st.session_state["_searched"] = True
        st.session_state.pop("_dismissed_keys_03", None)
        st.session_state.pop("_pdf_bytes_03", None)

_cur_03 = st.session_state["_col_order_03"]
if _cur_03:
    st.caption("Arrastrá para reordenar")
    _cur_03 = sort_items(_cur_03, key=f"sort_03_{abs(hash(frozenset(_cur_03)))}")
    st.session_state["_col_order_03"] = _cur_03
selected_labels = _cur_03
selected_keys   = [_label_to_col[lbl]["key"] for lbl in selected_labels if lbl in _label_to_col]

if not st.session_state.get("_searched"):
    st.stop()

st.divider()

# -- Carga y análisis ---------------------------------------------------------

try:
    with st.spinner("Analizando registros..."):
        all_facturas = get_all_records("fact_compra")
        obras        = get_all_records("dim_obra", columns="id, clave, nombre")
except Exception as exc:
    st.error(f"Error al cargar datos: {exc}")
    st.stop()

nm_obra: dict[int, str] = {r["id"]: (r.get("clave") or r.get("nombre") or str(r["id"])) for r in obras}

# _proveedor ya es texto directo en Supabase
for r in all_facturas:
    r["_proveedor"] = r.get("proveedor_texto") or "—"

if not all_facturas:
    st.info("No se encontraron registros en FactCompra.")
    st.stop()

inv_groups  = _detect_duplicates(all_facturas)
line_groups = _detect_line_duplicates(all_facturas)
dup_groups  = inv_groups + line_groups

if "_dismissed_keys_03" not in st.session_state:
    st.session_state["_dismissed_keys_03"] = _load_dismissed_keys()
_dismissed = st.session_state["_dismissed_keys_03"]
dup_groups = [g for g in dup_groups if _group_key(g) not in _dismissed]

if not dup_groups:
    st.success(f"✅ No se encontraron duplicados en **{len(all_facturas):,}** registros analizados.")
    st.stop()

# -- Métricas -----------------------------------------------------------------

_n_riesgo = sum(sum(len(e["records"]) for e in g["entries"][1:]) for g in dup_groups)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Registros analizados",  f"{len(all_facturas):,}")
m2.metric("Duplicados de factura", len(inv_groups))
m3.metric("Líneas duplicadas",     len(line_groups))
m4.metric("Registros en riesgo",   _n_riesgo)

st.divider()

# -- Grupos -------------------------------------------------------------------

_doc_groups: dict[tuple, list[tuple[int, dict]]] = {}
for _gi, _g in enumerate(dup_groups):
    _dk = (_g["nro_doc_norm"], _g["proveedor_raw"])
    _doc_groups.setdefault(_dk, []).append((_gi, _g))

for (nro, prov_raw), _issue_list in _doc_groups.items():
    prov_name = prov_raw  # ya es texto
    _doc_risk = sum(sum(len(e["records"]) for e in g["entries"][1:]) for _, g in _issue_list)
    _n_issues = len(_issue_list)
    _tag      = f"{_n_issues} problema{'s' if _n_issues > 1 else ''} · {_doc_risk} en riesgo"

    with st.container(border=True):
        st.markdown(f"""
<div class="js-grp-hdr">
  <div>
    <div class="js-grp-nro">{nro}</div>
    <div class="js-grp-prov">{prov_name}</div>
  </div>
  <span class="js-grp-tag">{_tag}</span>
</div>""", unsafe_allow_html=True)

        for _issue_idx, (gi, group) in enumerate(_issue_list):
            if _issue_idx > 0:
                st.divider()

            entries   = group["entries"]
            n_dups    = len(entries) - 1
            total_fmt = _fmt_gs(group["total"])
            orig      = entries[0]
            is_line   = group["type"] == "line"

            st.markdown(
                f'<p class="js-cap">{"Línea repetida" if is_line else "Factura duplicada"}'
                f' · Gs. {total_fmt}</p>',
                unsafe_allow_html=True,
            )

            for di, dup in enumerate(entries[1:], start=1):
                if di > 1:
                    st.markdown("---")

                pending_key = f"_pending_{gi}_{di}"

                if st.session_state.get(pending_key):
                    n_del = len(st.session_state[pending_key])
                    st.warning(f"⚠️ Vas a eliminar **{n_del} registro(s)**. Esta acción no se puede deshacer.")
                    bc1, bc2, _ = st.columns([1, 1, 5])
                    with bc1:
                        if st.button("✅ Confirmar", key=f"yes_{gi}_{di}", type="primary"):
                            items_to_del = st.session_state.pop(pending_key)
                            errors = []
                            for item in items_to_del:
                                try:
                                    # Eliminar de Airtable (fuente)
                                    at_delete_record("facturas", item["airtable_id"])
                                except Exception as e:
                                    errors.append(f"Airtable: {e}")
                                try:
                                    # Eliminar de Supabase
                                    delete_record("fact_compra", item["id"])
                                except Exception as e:
                                    errors.append(f"Supabase: {e}")
                            clear_cache()
                            at_get_all_records.clear()
                            st.session_state["_deleted_info"] = {
                                "count": 0 if errors else len(items_to_del),
                                "nro": nro,
                                "proveedor": prov_name,
                                **({"errors": errors} if errors else {}),
                            }
                            st.rerun()
                    with bc2:
                        if st.button("❌ Cancelar", key=f"no_{gi}_{di}"):
                            del st.session_state[pending_key]
                            st.rerun()
                    continue

                col_orig, col_dup = st.columns(2)

                with col_orig:
                    st.markdown('<span class="js-pill js-orig">Original</span>', unsafe_allow_html=True)
                    st.caption(
                        f"{orig['fecha_compra']} · "
                        f"creado {orig['min_created'].strftime('%d/%m/%Y %H:%M')} · "
                        f"{len(orig['records'])} línea(s)"
                    )
                    if selected_keys:
                        st.dataframe(
                            _build_df(orig["records"], selected_keys, nm_obra),
                            use_container_width=True, hide_index=True,
                        )
                    else:
                        st.caption("Activá columnas para ver el detalle.")

                with col_dup:
                    _dup_label = (
                        (f"Línea dup. {di}" if n_dups > 1 else "Línea dup.") if is_line
                        else (f"Duplicado {di}" if n_dups > 1 else "Duplicado")
                    )
                    _pill_cls = "js-line" if is_line else "js-dup"
                    st.markdown(f'<span class="js-pill {_pill_cls}">{_dup_label}</span>', unsafe_allow_html=True)
                    st.caption(
                        f"{dup['fecha_compra']} · "
                        f"creado {dup['min_created'].strftime('%d/%m/%Y %H:%M')} · "
                        f"{len(dup['records'])} línea(s)"
                    )
                    if selected_keys:
                        dup_df   = _build_df(dup["records"], selected_keys, nm_obra, include_delete_col=True)
                        non_edit = [c for c in dup_df.columns if c != "Eliminar"]
                        edited   = st.data_editor(
                            dup_df,
                            column_config={"Eliminar": st.column_config.CheckboxColumn(
                                "Eliminar", default=True, width="small"
                            )},
                            disabled=non_edit,
                            use_container_width=True, hide_index=True,
                            key=f"editor_{gi}_{di}",
                        )
                        to_delete_idx = [i for i, row in edited.iterrows() if row.get("Eliminar", False)]
                    else:
                        to_delete_idx = list(range(len(dup["records"])))
                        st.caption(f"{len(dup['records'])} línea(s) — activá columnas para ver el detalle.")

                # Guardar {id, airtable_id} para poder eliminar de ambos lados
                to_delete_items = [
                    {"id": dup["records"][i]["id"], "airtable_id": dup["records"][i]["airtable_id"]}
                    for i in to_delete_idx
                    if dup["records"][i].get("id") and dup["records"][i].get("airtable_id")
                ]

                if to_delete_items:
                    act1, act2, _ = st.columns([2, 2, 3])
                    with act1:
                        if st.button(f"🗑️ Eliminar {len(to_delete_items)} línea(s)", key=f"del_{gi}_{di}"):
                            st.session_state[pending_key] = to_delete_items
                            st.rerun()
                    with act2:
                        if st.button("🚫 No es duplicado", key=f"dismiss_{gi}_{di}"):
                            _dismiss_group(group, prov_name)
                            st.session_state["_dismissed_keys_03"].add(_group_key(group))
                            st.rerun()

# -- Reporte PDF --------------------------------------------------------------

st.divider()
st.download_button(
    label="📄 Descargar reporte PDF",
    data=_generate_duplicates_pdf(dup_groups, nm_obra),
    file_name=f"duplicados_factcompra_{datetime.today().strftime('%Y%m%d')}.pdf",
    mime="application/pdf",
)
