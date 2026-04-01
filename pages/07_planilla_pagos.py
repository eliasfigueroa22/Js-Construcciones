"""Tool 7 — Planilla de Pagos.

Planilla semanal de pagos agrupada por obra. El arquitecto arma
la planilla, consulta el contexto de cada trabajador y carga
selectivamente los registros a fact_pago en Supabase.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime

import pandas as pd
import streamlit as st

from connectors.supabase_connector import create_record, get_all_records, clear_cache
from core.base_tool import ToolMetadata
from generators.pdf_generator import generate_planilla_pagos_pdf

TOOL = ToolMetadata(
    name="Planilla de Pagos",
    description="Planilla semanal de pagos por obra y trabajador. Exportá a PDF y cargá a la base de datos.",
    icon="💸",
    page_file="07_planilla_pagos.py",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_METODO_OPTIONS   = ["Efectivo", "Transferencia"]
_TIPO_PAG_OPTIONS = ["PAGO", "ADELANTO", "PRODUCCION"]

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
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
.js-sub  { color: var(--js-muted); font-size: .875rem; margin-top: -10px; margin-bottom: 24px; }
.js-pill { display: inline-block; border-radius: 3px; padding: 2px 8px; font-size: .68rem;
           font-weight: 700; letter-spacing: .8px; text-transform: uppercase; }

/* Planilla table */
.pp-obra-hdr {
    background: #1a252f; color: white; font-weight: 700;
    padding: 7px 12px; border-radius: 4px 4px 0 0;
    font-size: .9rem; letter-spacing: .5px; text-transform: uppercase;
    margin-top: 12px;
}
.pp-col-hdr {
    display: grid;
    grid-template-columns: 32px 1fr 1fr 120px 110px 36px;
    gap: 6px;
    padding: 4px 8px;
    background: rgba(93,109,126,0.25);
    font-size: .72rem; font-weight: 700; color: var(--js-muted);
    text-transform: uppercase; letter-spacing: .5px;
}
.pp-subtotal {
    background: #d5d8dc; font-weight: 600;
    padding: 5px 12px; text-align: right;
    font-size: .82rem; color: #1a252f;
    border-top: 1px solid #aab7b8;
}
.pp-total-block {
    background: #aab7b8; font-weight: 700;
    padding: 8px 12px; border-radius: 0 0 4px 4px;
    margin-bottom: 8px;
}
.pp-total-main { font-size: 1rem; color: #1a252f; }
.pp-total-sub  { font-size: .82rem; color: #2e4053; margin-top: 3px; }
.pp-transf     { color: #E8622A; font-weight: 700; font-size: .82rem; }
.pp-efect      { color: #6B7280; font-size: .82rem; }
.pp-locked     { color: var(--js-muted); font-size: .75rem; }

/* Context card */
.pp-ctx {
    background: rgba(255,255,255,0.04);
    border-left: 3px solid var(--js-accent);
    border-radius: 0 4px 4px 0;
    padding: 9px 13px; margin: 8px 0 12px 0;
    font-size: .82rem; line-height: 1.7;
}
.pp-ctx b { color: rgba(255,255,255,0.85); }
.pp-ctx-bal-pos { color: #27AE60; font-weight: 600; }
.pp-ctx-bal-neg { color: #E74C3C; font-weight: 600; }
</style>
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v: float) -> str:
    """Formatea guaraníes: Gs. 1.234.567"""
    try:
        return f"Gs. {int(v):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Gs. 0"


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_ss():
    if "pago_fecha"  not in st.session_state:
        st.session_state["pago_fecha"]  = date.today()
    if "pago_lineas" not in st.session_state:
        st.session_state["pago_lineas"] = []
    if "pago_form_gen" not in st.session_state:
        st.session_state["pago_form_gen"] = 0
    if "pago_edit_buf" not in st.session_state:
        st.session_state["pago_edit_buf"] = None


# ---------------------------------------------------------------------------
# Context card
# ---------------------------------------------------------------------------

def _find_presupuesto(obra_id: int, trab_id: int, presup_raw) -> dict | None:
    """Retorna el mejor presupuesto para obra+trabajador (prioriza estado=Activo), o None."""
    matches = [
        r for r in presup_raw
        if r.get("obra_id") == obra_id
        and r.get("trabajador_id") == trab_id
    ]
    if not matches:
        return None
    activos = [r for r in matches if r.get("estado") == "Activo"]
    return activos[0] if activos else matches[-1]


def _context_card(
    obra_id: int, trab_id: int, pres_record: dict | None,
    pagos_raw, med_cabs_raw, med_lineas_raw,
) -> None:
    """Muestra el contexto del trabajador: retiro total en obra, balance del presupuesto, última medición."""

    # 1. Retiro acumulado total en esta obra
    retiro = sum(
        float(r.get("monto_pago", 0) or 0)
        for r in pagos_raw
        if r.get("obra_id") == obra_id
        and r.get("trabajador_id") == trab_id
    )

    # 2. Monto del presupuesto seleccionado
    pres_monto    = float(pres_record.get("monto_presupuestado", 0) or 0) if pres_record else None
    pres_concepto = pres_record.get("concepto", "") if pres_record else ""

    # 3. Última medición confirmada
    cabs = [
        c for c in med_cabs_raw
        if c.get("obra_id") == obra_id
        and c.get("trabajador_id") == trab_id
        and c.get("estado") == "Confirmado"
    ]
    ultima_med = None
    if cabs:
        last_cab_id = sorted(cabs, key=lambda x: x.get("fecha", "") or "", reverse=True)[0]["id"]
        ultima_med = sum(
            float(l.get("cantidad", 0) or 0) * float(l.get("precio_unitario", 0) or 0)
            for l in med_lineas_raw
            if l.get("cabecera_id") == last_cab_id
        )

    retiro_str = _fmt(retiro)
    med_str    = _fmt(ultima_med) if ultima_med is not None else "—"

    if pres_monto is not None:
        bal = pres_monto - retiro
        sign = "+" if bal >= 0 else ""
        css_cls = "pp-ctx-bal-pos" if bal >= 0 else "pp-ctx-bal-neg"
        pres_line = f"<b>Presupuesto seleccionado:</b> {_fmt(pres_monto)}"
        if pres_concepto:
            pres_line += f'<br><span style="font-size:.75rem;color:#6B7280">{pres_concepto}</span>'
        bal_line = f'<b>Balance (presupuesto − retiro):</b> <span class="{css_cls}">{sign}{_fmt(bal)}</span>'
    else:
        pres_line = "<b>Presupuesto:</b> <span style='color:#6B7280'>Sin presupuesto</span>"
        bal_line  = "<b>Balance:</b> —"

    st.markdown(
        f"""<div class="pp-ctx">
        <b>Retiro acumulado en obra:</b> {retiro_str}<br>
        {pres_line}<br>
        {bal_line}<br>
        <b>Última medición (total Gs.):</b> {med_str}
        </div>""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Tab 1 — Planilla
# ---------------------------------------------------------------------------

def _render_tab_planilla(
    obras_raw, trab_raw, pagos_raw, presup_raw, med_cabs_raw, med_lineas_raw,
    sectores_raw, rubros_raw,
):
    # Mapas completos (incluye todas las obras para resolver IDs en la tabla ya cargada)
    obra_id_to_name_full = {
        r["id"]: r.get("clave") or r.get("nombre", str(r["id"]))
        for r in obras_raw
    }
    obra_name_to_id_full = {v: k for k, v in obra_id_to_name_full.items()}
    trab_id_to_name = {
        r["id"]: r.get("nombre_completo", str(r["id"]))
        for r in trab_raw
    }
    trab_name_to_id = {v: k for k, v in trab_id_to_name.items()}

    # Filtro por estado
    estado_vals = sorted({r.get("estado_obra", "") for r in obras_raw if r.get("estado_obra")})
    default_estado_idx = next(
        (i for i, v in enumerate(estado_vals) if v.lower().startswith("activ")), 0
    )
    sel_estado = st.radio(
        "Estado de obras",
        estado_vals + ["Todas"],
        index=default_estado_idx,
        horizontal=True,
        key="pp_estado_filter",
        label_visibility="collapsed",
    )
    obras_filtradas = [
        r for r in obras_raw
        if sel_estado == "Todas" or r.get("estado_obra") == sel_estado
    ]

    obra_id_to_name = {
        r["id"]: r.get("clave") or r.get("nombre", str(r["id"]))
        for r in obras_filtradas
    }
    obra_name_to_id = {v: k for k, v in obra_id_to_name.items()}
    obra_options = sorted(obra_name_to_id)
    trab_options = sorted(trab_name_to_id)

    # ── Fecha y título ────────────────────────────────────────────────────
    fecha = st.date_input(
        "Fecha de la planilla",
        value=st.session_state["pago_fecha"],
        format="MM/DD/YYYY",
        key="pago_fecha_input",
        label_visibility="collapsed",
    )
    st.session_state["pago_fecha"] = fecha
    fecha_str = f"{fecha.day}/{fecha.month:02d}/{fecha.year}"
    st.subheader(f"Planilla de Pagos {fecha_str}")

    lineas: list[dict] = st.session_state["pago_lineas"]
    gen = st.session_state["pago_form_gen"]
    edit_buf = st.session_state.get("pago_edit_buf")
    is_editing = edit_buf is not None

    col_form, col_tabla = st.columns([1, 2], gap="large")

    # ── Formulario ────────────────────────────────────────────────────────
    with col_form:
        with st.container(border=True):
            st.markdown("**Editar pago**" if is_editing else "**Agregar pago**")

            if is_editing:
                edit_obra_name = obra_id_to_name_full.get(edit_buf["obra_id"], "")
                edit_trab_name = trab_id_to_name.get(edit_buf["trab_id"], "")
                obra_opts_edit = sorted({edit_obra_name} | set(obra_options)) if edit_obra_name else obra_options
                trab_opts_edit = trab_options
                obra_def_idx = (obra_opts_edit.index(edit_obra_name) + 1) if edit_obra_name in obra_opts_edit else 0
                trab_def_idx = (trab_opts_edit.index(edit_trab_name) + 1) if edit_trab_name in trab_opts_edit else 0
            else:
                obra_opts_edit = obra_options
                trab_opts_edit = trab_options
                obra_def_idx = 0
                trab_def_idx = 0

            _obra_key  = "pf_obra_edit"     if is_editing else "pf_obra"
            _trab_key  = "pf_trab_edit"     if is_editing else "pf_trab"
            _met_key   = "pf_metodo_edit"   if is_editing else "pf_metodo"
            _tipo_key  = "pf_tipo_edit"     if is_editing else "pf_tipo"
            _conc_key  = "pf_concepto_edit" if is_editing else f"pf_concepto_{gen}"
            _monto_key = "pf_monto_edit"    if is_editing else f"pf_monto_{gen}"

            sel_obra = st.selectbox(
                "Obra", ["— seleccionar —"] + obra_opts_edit, index=obra_def_idx, key=_obra_key,
            )
            sel_trab = st.selectbox(
                "Trabajador", ["— seleccionar —"] + trab_opts_edit, index=trab_def_idx, key=_trab_key,
            )

            sel_obra_id = obra_name_to_id_full.get(sel_obra) if sel_obra != "— seleccionar —" else None
            sel_trab_id = trab_name_to_id.get(sel_trab)      if sel_trab != "— seleccionar —" else None

            # ── Selector de presupuesto ───────────────────────────────────
            sel_presup_id  = None
            sel_sector_id  = None
            sel_rubro_id   = None
            sel_pres_record = None

            if sel_obra_id and sel_trab_id:
                _SIN_PRES = "— Sin presupuesto"
                pres_matches = [
                    r for r in presup_raw
                    if r.get("obra_id") == sel_obra_id
                    and r.get("trabajador_id") == sel_trab_id
                ]

                def _pres_label(p: dict) -> str:
                    conc   = p.get("concepto", "") or ""
                    monto_ = float(p.get("monto_presupuestado", 0) or 0)
                    estado = p.get("estado", "") or ""
                    label  = conc if conc else "Presupuesto"
                    label += f" — {_fmt(monto_)}"
                    if estado:
                        label += f" [{estado}]"
                    return label

                pres_labels = [_pres_label(p) for p in pres_matches] + [_SIN_PRES]

                if is_editing and edit_buf.get("presup_id"):
                    default_pres_idx = next(
                        (i for i, p in enumerate(pres_matches) if p["id"] == edit_buf["presup_id"]),
                        len(pres_labels) - 1,
                    )
                elif pres_matches:
                    default_pres_idx = next(
                        (i for i, p in enumerate(pres_matches) if p.get("estado") == "Activo"), 0
                    )
                else:
                    default_pres_idx = 0

                _pres_key = "pf_pres_edit" if is_editing else f"pf_pres_{gen}"

                if pres_matches:
                    st.markdown(
                        '<span style="font-size:.8rem;font-weight:600;color:rgba(255,255,255,.7)">Presupuesto</span>',
                        unsafe_allow_html=True,
                    )
                    sel_pres_label = st.radio(
                        "Presupuesto", pres_labels,
                        index=default_pres_idx,
                        key=_pres_key,
                        label_visibility="collapsed",
                    )
                    if sel_pres_label != _SIN_PRES:
                        pres_idx = pres_labels.index(sel_pres_label)
                        sel_pres_record = pres_matches[pres_idx]
                        sel_presup_id  = sel_pres_record["id"]
                        sel_sector_id  = sel_pres_record.get("sector_id")
                        sel_rubro_id   = sel_pres_record.get("rubro_id")
                else:
                    sel_pres_label = _SIN_PRES

                # ── Selectores manuales de sector/rubro (Sin presupuesto) ─
                if sel_pres_label == _SIN_PRES:
                    obra_sectores = [
                        r for r in sectores_raw
                        if r.get("obra_id") == sel_obra_id
                    ]
                    sec_name_to_id = {
                        r.get("nombre_sector", ""): r["id"]
                        for r in obra_sectores
                        if r.get("nombre_sector")
                    }
                    sec_id_to_name = {v: k for k, v in sec_name_to_id.items()}
                    sec_opts = ["— sin sector —"] + sorted(sec_name_to_id)

                    rub_name_to_id = {
                        f"{r.get('rubro','')} — {r.get('nombre_completo','')}": r["id"]
                        for r in rubros_raw
                        if r.get("rubro")
                    }
                    rub_opts = ["— sin rubro —"] + sorted(rub_name_to_id)

                    _sec_key = "pf_sec_edit" if is_editing else f"pf_sec_{gen}"
                    _rub_key = "pf_rub_edit" if is_editing else f"pf_rub_{gen}"

                    sec_def = 0
                    rub_def = 0
                    if is_editing and edit_buf.get("sector_id"):
                        sec_name = sec_id_to_name.get(edit_buf["sector_id"], "")
                        if sec_name in sec_opts:
                            sec_def = sec_opts.index(sec_name)
                    if is_editing and edit_buf.get("rubro_id"):
                        rub_match = next(
                            (lbl for lbl, rid in rub_name_to_id.items() if rid == edit_buf["rubro_id"]), ""
                        )
                        if rub_match in rub_opts:
                            rub_def = rub_opts.index(rub_match)

                    sel_sec = st.selectbox("Sector", sec_opts, index=sec_def, key=_sec_key)
                    sel_rub = st.selectbox("Rubro",  rub_opts, index=rub_def, key=_rub_key)
                    sel_sector_id = sec_name_to_id.get(sel_sec) if sel_sec != "— sin sector —" else None
                    sel_rubro_id  = rub_name_to_id.get(sel_rub) if sel_rub != "— sin rubro —"  else None

                # Context card
                _context_card(
                    sel_obra_id, sel_trab_id, sel_pres_record,
                    pagos_raw, med_cabs_raw, med_lineas_raw,
                )

            concepto = st.text_input(
                "Concepto",
                value=edit_buf["concepto"] if is_editing else "",
                placeholder="Ej: Retiro de dinero, anticipo pintura…",
                key=_conc_key,
            )
            monto = st.number_input(
                "Monto (Gs.)",
                value=int(edit_buf["monto"]) if is_editing else 0,
                min_value=0, step=50_000, format="%d",
                key=_monto_key,
            )
            if monto > 0:
                st.caption(f"= {_fmt(monto)}")

            met_def  = _METODO_OPTIONS.index(edit_buf["metodo"])      if is_editing and edit_buf["metodo"]    in _METODO_OPTIONS    else 0
            tipo_def = _TIPO_PAG_OPTIONS.index(edit_buf["tipo_pago"]) if is_editing and edit_buf["tipo_pago"] in _TIPO_PAG_OPTIONS else 0
            metodo = st.selectbox("Método de pago", _METODO_OPTIONS,   index=met_def,  key=_met_key)
            tipo   = st.selectbox("Tipo de pago",   _TIPO_PAG_OPTIONS, index=tipo_def, key=_tipo_key)

            can_add = bool(sel_obra_id and sel_trab_id and monto > 0)

            if is_editing:
                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("💾 Guardar cambios", type="primary", disabled=not can_add, use_container_width=True):
                        for i, l in enumerate(st.session_state["pago_lineas"]):
                            if l["uid"] == edit_buf["uid"]:
                                st.session_state["pago_lineas"][i].update({
                                    "obra_id":   sel_obra_id,
                                    "trab_id":   sel_trab_id,
                                    "concepto":  concepto.strip(),
                                    "monto":     float(monto),
                                    "metodo":    metodo,
                                    "tipo_pago": tipo,
                                    "presup_id": sel_presup_id,
                                    "sector_id": sel_sector_id,
                                    "rubro_id":  sel_rubro_id,
                                })
                                break
                        st.session_state["pago_edit_buf"] = None
                        st.rerun()
                with bcol2:
                    if st.button("✖ Cancelar", use_container_width=True):
                        st.session_state["pago_edit_buf"] = None
                        st.rerun()
            else:
                if st.button("➕ Agregar", type="primary", disabled=not can_add, use_container_width=True):
                    st.session_state["pago_lineas"].append({
                        "uid":         uuid.uuid4().hex,
                        "obra_id":     sel_obra_id,
                        "trab_id":     sel_trab_id,
                        "concepto":    concepto.strip(),
                        "monto":       float(monto),
                        "metodo":      metodo,
                        "tipo_pago":   tipo,
                        "include":     True,
                        "saved_to_db": False,
                        "presup_id":   sel_presup_id,
                        "sector_id":   sel_sector_id,
                        "rubro_id":    sel_rubro_id,
                    })
                    st.session_state["pago_form_gen"] += 1
                    st.rerun()

    # ── Tabla planilla ─────────────────────────────────────────────────────
    with col_tabla:
        if not lineas:
            st.info("La planilla está vacía. Agregá pagos desde el formulario.")
        else:
            uid_to_idx = {l["uid"]: i for i, l in enumerate(lineas)}

            by_obra: dict[int, list] = defaultdict(list)
            for line in lineas:
                by_obra[line["obra_id"]].append(line)

            for obra_id, obra_lines in by_obra.items():
                obra_name = obra_id_to_name_full.get(obra_id, str(obra_id))

                st.markdown(f'<div class="pp-obra-hdr">{obra_name}</div>', unsafe_allow_html=True)

                h0, h1, h2, h3, h4, h5, h6 = st.columns([0.6, 3, 3, 2, 2, 0.6, 0.6])
                for col, lbl in [(h0, ""), (h1, "Trabajador"), (h2, "Concepto"),
                                  (h3, "Monto"), (h4, "Método"), (h5, ""), (h6, "")]:
                    col.markdown(
                        f'<span style="font-size:.72rem;font-weight:700;color:#6B7280;'
                        f'text-transform:uppercase">{lbl}</span>',
                        unsafe_allow_html=True,
                    )

                obra_total = 0.0
                for line in obra_lines:
                    idx = uid_to_idx[line["uid"]]
                    c0, c1, c2, c3, c4, c5, c6 = st.columns([0.6, 3, 3, 2, 2, 0.6, 0.6])

                    if line["saved_to_db"]:
                        c0.markdown('<span class="pp-locked">🔒</span>', unsafe_allow_html=True)
                    else:
                        new_inc = c0.checkbox(
                            "", value=line["include"],
                            key=f"pp_inc_{line['uid']}",
                            label_visibility="collapsed",
                        )
                        if new_inc != line["include"]:
                            st.session_state["pago_lineas"][idx]["include"] = new_inc
                            st.rerun()

                    c1.write(trab_id_to_name.get(line["trab_id"], str(line["trab_id"])))
                    c2.write(line["concepto"] or "—")
                    c3.write(_fmt(line["monto"]))

                    if line["metodo"] == "Transferencia":
                        c4.markdown('<span class="pp-transf">TRANSFERENCIA</span>', unsafe_allow_html=True)
                    else:
                        c4.markdown('<span class="pp-efect">EFECTIVO</span>', unsafe_allow_html=True)

                    if not line["saved_to_db"]:
                        if c5.button("✏️", key=f"pp_edit_{line['uid']}", help="Editar fila"):
                            st.session_state["pago_edit_buf"] = {**line}
                            st.rerun()
                        if c6.button("🗑️", key=f"pp_del_{line['uid']}", help="Eliminar fila"):
                            st.session_state["pago_lineas"].pop(idx)
                            if st.session_state.get("pago_edit_buf") and \
                               st.session_state["pago_edit_buf"].get("uid") == line["uid"]:
                                st.session_state["pago_edit_buf"] = None
                            st.rerun()

                    obra_total += line["monto"]

                st.markdown(
                    f'<div class="pp-subtotal">Subtotal {obra_name}: <b>{_fmt(obra_total)}</b></div>',
                    unsafe_allow_html=True,
                )

            grand_total    = sum(l["monto"] for l in lineas)
            efectivo_total = sum(l["monto"] for l in lineas if l["metodo"] == "Efectivo")
            transfer_total = sum(l["monto"] for l in lineas if l["metodo"] == "Transferencia")

            st.markdown(
                f"""<div class="pp-total-block">
                <div class="pp-total-main">TOTAL GENERAL: <b>{_fmt(grand_total)}</b></div>
                <div class="pp-total-sub">
                  Efectivo: {_fmt(efectivo_total)} &nbsp;·&nbsp; Transferencia: {_fmt(transfer_total)}
                </div>
                </div>""",
                unsafe_allow_html=True,
            )

    # ── Botones de acción ─────────────────────────────────────────────────
    if lineas:
        st.divider()
        n_pendientes = sum(1 for l in lineas if l.get("include") and not l.get("saved_to_db"))
        btn_pdf, btn_cargar, _ = st.columns([1, 1, 3])

        with btn_pdf:
            pdf_bytes = generate_planilla_pagos_pdf(
                lineas=lineas,
                fecha=st.session_state["pago_fecha"],
                obra_names=obra_id_to_name_full,
                trab_names=trab_id_to_name,
            )
            fname = f"Planilla de Pagos {fecha_str.replace('/', '-')}.pdf"
            st.download_button(
                "📄 Exportar PDF",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                use_container_width=True,
            )

        with btn_cargar:
            if st.button(
                f"📤 Cargar a BD ({n_pendientes})",
                type="primary",
                disabled=(n_pendientes == 0),
                use_container_width=True,
            ):
                _cargar_a_bd(obra_id_to_name_full, trab_id_to_name)


def _cargar_a_bd(obra_id_to_name: dict, trab_id_to_name: dict) -> None:
    """Carga a fact_pago todas las filas seleccionadas y no guardadas."""
    lineas  = st.session_state["pago_lineas"]
    fecha   = st.session_state["pago_fecha"]
    fecha_s = fecha.isoformat()

    saved_msgs = []
    error_msgs = []

    for i, line in enumerate(lineas):
        if not line.get("include") or line.get("saved_to_db"):
            continue

        fields: dict = {
            "obra_id":       line["obra_id"],
            "trabajador_id": line["trab_id"],
            "fecha_pago":    fecha_s,
            "concepto":      line.get("concepto", ""),
            "monto_pago":    line["monto"],
            "metodo_pago":   line["metodo"],
            "tipo_pago":     line.get("tipo_pago", "PAGO"),
        }
        if line.get("presup_id"):
            fields["presupuesto_subcontratista_id"] = line["presup_id"]
        if line.get("sector_id"):
            fields["sector_id"] = line["sector_id"]
        if line.get("rubro_id"):
            fields["rubro_id"] = line["rubro_id"]

        try:
            create_record("fact_pago", fields)
            st.session_state["pago_lineas"][i]["saved_to_db"] = True
            st.session_state["pago_lineas"][i]["include"]     = False
            trab_name = trab_id_to_name.get(line["trab_id"], "?")
            obra_name = obra_id_to_name.get(line["obra_id"], "?")
            saved_msgs.append(f"• {trab_name} — {obra_name}: {_fmt(line['monto'])}")
        except Exception as e:
            trab_name = trab_id_to_name.get(line["trab_id"], "?")
            error_msgs.append(f"• {trab_name}: {e}")

    # Invalidar caché para que Tab 2 muestre datos frescos
    clear_cache()

    if saved_msgs:
        st.success(f"Se guardaron {len(saved_msgs)} pago(s):\n" + "\n".join(saved_msgs))
    if error_msgs:
        st.error("Errores al guardar:\n" + "\n".join(error_msgs))

    st.rerun()


# ---------------------------------------------------------------------------
# Tab 2 — Consultar Trabajador
# ---------------------------------------------------------------------------

def _render_tab_consultar(
    obras_raw, trab_raw, pagos_raw, presup_raw, med_cabs_raw, med_lineas_raw,
):
    nm_obra = {r["id"]: r.get("clave") or r.get("nombre", str(r["id"])) for r in obras_raw}
    obra_name_to_id = {v: k for k, v in nm_obra.items()}
    nm_trab = {r["id"]: r.get("nombre_completo", str(r["id"])) for r in trab_raw}
    trab_name_to_id = {v: k for k, v in nm_trab.items()}

    obra_options = sorted(obra_name_to_id)
    trab_options = sorted(trab_name_to_id)

    st.subheader("Consultar historial de trabajador")
    st.markdown(
        '<p class="js-sub">Consultá retiros, presupuesto y mediciones de un trabajador antes de hacer el pago.</p>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        q_trab = st.selectbox(
            "Trabajador (requerido)",
            ["— seleccionar —"] + trab_options,
            key="qt_trab",
        )
    with c2:
        q_obra = st.selectbox(
            "Obra (opcional — todas)",
            ["Todas las obras"] + obra_options,
            key="qt_obra",
        )

    q_trab_id = trab_name_to_id.get(q_trab) if q_trab != "— seleccionar —" else None
    q_obra_id = obra_name_to_id.get(q_obra) if q_obra != "Todas las obras" else None

    if not q_trab_id:
        st.info("Seleccioná un trabajador para ver su historial.")
        return

    # ── Filtrar datos ─────────────────────────────────────────────────────
    trab_pagos = [
        r for r in pagos_raw
        if r.get("trabajador_id") == q_trab_id
        and (q_obra_id is None or r.get("obra_id") == q_obra_id)
    ]
    total_pagado = sum(float(r.get("monto_pago", 0) or 0) for r in trab_pagos)

    trab_pres = [
        r for r in presup_raw
        if r.get("trabajador_id") == q_trab_id
        and (q_obra_id is None or r.get("obra_id") == q_obra_id)
    ]
    activos   = [r for r in trab_pres if r.get("estado") == "Activo"]
    pres_ppal = activos[0] if activos else (trab_pres[-1] if trab_pres else None)
    pres_activo = float(pres_ppal.get("monto_presupuestado", 0) or 0) if pres_ppal else None

    trab_cabs = [
        c for c in med_cabs_raw
        if c.get("trabajador_id") == q_trab_id
        and (q_obra_id is None or c.get("obra_id") == q_obra_id)
        and c.get("estado") == "Confirmado"
    ]
    cab_ids_set = {c["id"] for c in trab_cabs}
    trab_lineas = [
        l for l in med_lineas_raw
        if l.get("cabecera_id") in cab_ids_set
    ]
    total_med = sum(
        float(l.get("cantidad", 0) or 0) * float(l.get("precio_unitario", 0) or 0)
        for l in trab_lineas
    )

    # ── Metric cards ─────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Pagado", _fmt(total_pagado))

    if pres_activo is not None:
        balance = pres_activo - total_pagado
        m2.metric("Presupuesto Activo", _fmt(pres_activo))
        sign = "+" if balance >= 0 else ""
        m3.metric(
            "Balance",
            _fmt(balance),
            delta=f"{sign}{int(balance):,}".replace(",", "."),
        )
    else:
        m2.metric("Presupuesto Activo", "—")
        m3.metric("Balance", "—")

    m4.metric("Total Mediciones", _fmt(total_med) if total_med else "—")

    # ── Últimos pagos ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("Últimos pagos")
    if trab_pagos:
        rows_pagos = []
        for r in trab_pagos:
            rows_pagos.append({
                "Fecha":    r.get("fecha_pago", ""),
                "Obra":     nm_obra.get(r.get("obra_id"), str(r.get("obra_id", ""))),
                "Concepto": r.get("concepto", ""),
                "Monto":    float(r.get("monto_pago", 0) or 0),
                "Método":   r.get("metodo_pago", ""),
                "Tipo":     r.get("tipo_pago", ""),
            })
        df_pagos = (
            pd.DataFrame(rows_pagos)
            .sort_values("Fecha", ascending=False)
            .reset_index(drop=True)
        )
        st.dataframe(df_pagos, use_container_width=True, hide_index=True)
    else:
        st.info("Sin pagos registrados para este trabajador.")

    # ── Mediciones ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Mediciones confirmadas")
    if trab_cabs:
        cab_lineas_by_id: dict = defaultdict(list)
        for l in trab_lineas:
            cab_lineas_by_id[l.get("cabecera_id")].append(l)

        rows_med = []
        for c in sorted(trab_cabs, key=lambda x: x.get("fecha", "") or "", reverse=True):
            c_lineas = cab_lineas_by_id.get(c["id"], [])
            total_c  = sum(
                float(l.get("cantidad", 0) or 0) * float(l.get("precio_unitario", 0) or 0)
                for l in c_lineas
            )
            rows_med.append({
                "Fecha":     c.get("fecha", ""),
                "Obra":      nm_obra.get(c.get("obra_id"), str(c.get("obra_id", ""))),
                "Estado":    c.get("estado", ""),
                "Total Gs.": total_c,
            })
        st.dataframe(pd.DataFrame(rows_med), use_container_width=True, hide_index=True)
    else:
        st.info("Sin mediciones confirmadas para este trabajador.")

    # ── Presupuestos ──────────────────────────────────────────────────────
    with st.expander("Presupuestos"):
        if trab_pres:
            rows_pres = []
            for r in trab_pres:
                rows_pres.append({
                    "Obra":     nm_obra.get(r.get("obra_id"), str(r.get("obra_id", ""))),
                    "Concepto": r.get("concepto", ""),
                    "Monto":    float(r.get("monto_presupuestado", 0) or 0),
                    "Estado":   r.get("estado", ""),
                })
            st.dataframe(pd.DataFrame(rows_pres), use_container_width=True, hide_index=True)
        else:
            st.write("Sin presupuestos registrados.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(layout="wide", page_title="Planilla de Pagos")
    st.markdown(_CSS, unsafe_allow_html=True)

    st.title("💸 Planilla de Pagos")
    st.markdown(
        '<p class="js-sub">Armá la planilla semanal, consultá el contexto de cada trabajador y cargá a la base de datos.</p>',
        unsafe_allow_html=True,
    )

    _init_ss()

    try:
        with st.spinner("Cargando datos…"):
            obras_raw      = get_all_records("dim_obra")
            trab_raw       = get_all_records("dim_trabajador")
            pagos_raw      = get_all_records("fact_pago")
            presup_raw     = get_all_records("fact_presupuesto_subcontratista")
            med_cabs_raw   = get_all_records("op_medicion_cabecera")
            med_lineas_raw = get_all_records("op_medicion_linea")
            sectores_raw   = get_all_records("dim_sector")
            rubros_raw     = get_all_records("dim_rubro")
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        st.stop()

    tab1, tab2 = st.tabs(["✏️ Planilla", "📊 Consultar Trabajador"])

    with tab1:
        _render_tab_planilla(
            obras_raw, trab_raw, pagos_raw, presup_raw, med_cabs_raw, med_lineas_raw,
            sectores_raw, rubros_raw,
        )

    with tab2:
        _render_tab_consultar(
            obras_raw, trab_raw, pagos_raw, presup_raw, med_cabs_raw, med_lineas_raw,
        )


main()
