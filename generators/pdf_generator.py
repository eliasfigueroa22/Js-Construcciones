"""Generador de reportes PDF con reportlab.

Produce tablas A4 con encabezados repetidos, filas alternadas,
texto con wrapping, y formato numérico paraguayo (separador de miles con punto).
"""

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas as rl_canvas

_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"

_styles = getSampleStyleSheet()

_CELL_STYLE = ParagraphStyle(
    "CellStyle",
    parent=_styles["Normal"],
    fontSize=7,
    leading=9,
)

_CELL_BOLD_STYLE = ParagraphStyle(
    "CellBoldStyle",
    parent=_styles["Normal"],
    fontSize=7,
    leading=9,
    fontName="Helvetica-Bold",
)

_HEADER_STYLE = ParagraphStyle(
    "HeaderStyle",
    parent=_styles["Normal"],
    fontSize=8,
    leading=10,
    fontName="Helvetica-Bold",
    textColor=colors.white,
)

_SECTION_TITLE = ParagraphStyle(
    "SectionTitle",
    parent=_styles["Heading2"],
    fontSize=11,
    spaceAfter=3 * mm,
    spaceBefore=6 * mm,
)



def _fmt_guaranies(value) -> str:
    """Formatea un número al estilo paraguayo: 1.234.567."""
    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


def _safe(text) -> str:
    """Escapa caracteres XML para Paragraph."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_table(
    columns: list[dict],
    rows: list[dict],
    available_width: float,
    *,
    show_totals: bool = False,
) -> Table:
    """Construye una Table con Paragraphs para wrapping automático.

    Si show_totals=True, agrega una fila TOTAL al final sumando
    las columnas con format="guaranies".
    """
    col_widths = [c["width_mm"] * mm for c in columns]

    # Escalar si excede el ancho disponible
    total_w = sum(col_widths)
    if total_w > available_width:
        scale = available_width / total_w
        col_widths = [w * scale for w in col_widths]

    header = [Paragraph(_safe(c["label"]), _HEADER_STYLE) for c in columns]
    data = [header]

    for row in rows:
        data_row = []
        for col in columns:
            val = row.get(col["key"], "")
            if col.get("format") == "guaranies":
                val = _fmt_guaranies(val)
            data_row.append(Paragraph(_safe(val), _CELL_STYLE))
        data.append(data_row)

    # Fila de totales
    has_totals_row = False
    if show_totals and rows:
        totals_row = []
        placed_label = False
        for col in columns:
            if col.get("format") == "guaranies":
                try:
                    col_sum = sum(float(r.get(col["key"], 0) or 0) for r in rows)
                    totals_row.append(Paragraph(_safe(_fmt_guaranies(col_sum)), _CELL_BOLD_STYLE))
                    has_totals_row = True
                except (ValueError, TypeError):
                    totals_row.append(Paragraph("", _CELL_STYLE))
            elif not placed_label:
                totals_row.append(Paragraph("<b>TOTAL</b>", _CELL_BOLD_STYLE))
                placed_label = True
            else:
                totals_row.append(Paragraph("", _CELL_STYLE))
        if has_totals_row:
            data.append(totals_row)

    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(
                ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#ecf0f1"))
            )

    # Estilo de la fila de totales
    if has_totals_row:
        totals_idx = len(data) - 1
        style_cmds.append(("BACKGROUND", (0, totals_idx), (-1, totals_idx), colors.HexColor("#d5dbdb")))
        style_cmds.append(("LINEABOVE", (0, totals_idx), (-1, totals_idx), 1.5, colors.HexColor("#2c3e50")))

    table.setStyle(TableStyle(style_cmds))
    return table


def generate_report_pdf(
    title: str,
    columns: list[dict],
    rows: list[dict],
    *,
    summary: dict | None = None,
) -> bytes:
    """Genera un PDF con tabla de datos.

    Args:
        title: Título del reporte.
        columns: Lista de dicts con keys "key", "label", "width_mm",
                 y opcionalmente "format" ("guaranies").
        rows: Lista de dicts con los datos.
        summary: Dict opcional con pares clave-valor para mostrar
                 antes de la tabla.

    Returns:
        Contenido del PDF como bytes.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30 * mm,
        rightMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
    )

    available_width = A4[0] - 50 * mm
    story: list = []

    story.append(Paragraph(title, _styles["Title"]))
    story.append(Spacer(1, 6 * mm))

    if summary:
        for label, value in summary.items():
            story.append(Paragraph(f"<b>{label}:</b> {value}", _styles["Normal"]))
        story.append(Spacer(1, 4 * mm))

    story.append(_build_table(columns, rows, available_width, show_totals=True))

    doc.build(story)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Reporte de Obra — hierarchical PDF with logo header and page numbers
# ---------------------------------------------------------------------------

_C_OBRA   = colors.HexColor("#1a252f")
_C_SECTOR = colors.HexColor("#2e4053")
_C_RUBRO  = colors.HexColor("#5d6d7e")
_C_SUB    = colors.HexColor("#d5d8dc")
_C_ALT    = colors.HexColor("#f2f3f4")
_C_TOTAL  = colors.HexColor("#aab7b8")

_WH = colors.white
_DK = colors.HexColor("#1a252f")

_OR_OBRA        = ParagraphStyle("ORObraStyle",    parent=_styles["Normal"], fontSize=8,   fontName="Helvetica-Bold", textColor=_WH)
_OR_SECTOR      = ParagraphStyle("ORSectorStyle",  parent=_styles["Normal"], fontSize=7.5, fontName="Helvetica-Bold", textColor=_WH)
_OR_RUBRO       = ParagraphStyle("ORRubroStyle",   parent=_styles["Normal"], fontSize=7,   fontName="Helvetica-Bold", textColor=_WH)
_OR_RUBRO_RESUMEN = ParagraphStyle("ORRubroRes",   parent=_styles["Normal"], fontSize=7,   fontName="Helvetica-Bold", textColor=_DK)
_OR_ITEM        = ParagraphStyle("ORItemStyle",    parent=_styles["Normal"], fontSize=7,   leading=9)
_OR_SUB         = ParagraphStyle("ORSubStyle",     parent=_styles["Normal"], fontSize=7,   fontName="Helvetica-Bold")
_OR_HDR         = ParagraphStyle("ORHdrStyle",     parent=_styles["Normal"], fontSize=7.5, fontName="Helvetica-Bold", textColor=_WH)


class _NumberedCanvas(rl_canvas.Canvas):
    """Canvas que escribe 'Página X de Y' al final de cada página."""

    def __init__(self, *args, **kwargs):
        rl_canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)

    def _draw_page_number(self, total: int):
        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor("#6B7280"))
        self.drawCentredString(A4[0] / 2, 12 * mm, f"Página {self._pageNumber} de {total}")


def _obra_page_template(canvas_obj, doc, title: str, subtitle: str, fecha: str):
    """Header común para todas las páginas del reporte de obra."""
    canvas_obj.saveState()

    top = A4[1]

    # Logo (si existe)
    if _LOGO_PATH.exists():
        canvas_obj.drawImage(
            str(_LOGO_PATH),
            30 * mm, top - 18 * mm,
            width=28 * mm, height=11 * mm,
            preserveAspectRatio=True, mask="auto",
        )

    # Título centrado
    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.setFillColor(_DK)
    canvas_obj.drawCentredString(A4[0] / 2, top - 14 * mm, title)

    # Fecha (derecha)
    canvas_obj.setFont("Helvetica-Bold", 8)
    canvas_obj.setFillColor(_DK)
    canvas_obj.drawRightString(A4[0] - 20 * mm, top - 11 * mm, f"Generado: {fecha}")

    # Subtítulo
    canvas_obj.setFont("Helvetica", 8.5)
    canvas_obj.setFillColor(colors.HexColor("#5d6d7e"))
    canvas_obj.drawCentredString(A4[0] / 2, top - 20 * mm, subtitle)

    # Línea separadora
    canvas_obj.setStrokeColor(colors.HexColor("#E8622A"))
    canvas_obj.setLineWidth(1.2)
    canvas_obj.line(30 * mm, top - 23 * mm, A4[0] - 20 * mm, top - 23 * mm)

    canvas_obj.restoreState()


def _build_obra_table(data_rows: list, col_widths: list[float]) -> Table:
    """Construye un Table a partir de filas ya formateadas con metadatos de estilo."""
    table = Table(data_rows, colWidths=col_widths, repeatRows=1)
    cmds = []
    for i, row_meta in enumerate(data_rows):
        if not isinstance(row_meta, tuple):
            continue
    table.setStyle(TableStyle(cmds))
    return table


def _p(text, style) -> Paragraph:
    s = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(s, style)


def _fmt_gs(value) -> str:
    try:
        return f"Gs. {int(float(value)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "---"


def _build_resumen_table(
    resumen: dict,  # {obra: {sector: {rubro: {mat, mo}}}}
    obra_nombre: str,
    available_width: float,
) -> Table:
    """Tabla jerárquica: Obra → Sector → Rubro | Materiales | MO | MAT+MO."""
    W = available_width
    col_widths = [W * 0.40, W * 0.20, W * 0.20, W * 0.20]

    # Header
    header = [
        _p("Obra / Sector / Rubro", _OR_HDR),
        _p("Materiales", _OR_HDR),
        _p("Mano de Obra", _OR_HDR),
        _p("MAT + MO", _OR_HDR),
    ]
    rows = [header]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _C_RUBRO),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]

    total_mat = total_mo = 0.0

    # Obra row
    obra_data = resumen.get(obra_nombre, {})
    rows.append([_p(obra_nombre, _OR_OBRA), _p("", _OR_OBRA), _p("", _OR_OBRA), _p("", _OR_OBRA)])
    obra_row_idx = len(rows) - 1
    style_cmds.append(("BACKGROUND", (0, obra_row_idx), (-1, obra_row_idx), _C_OBRA))

    for sector, rubros in sorted(obra_data.items(), key=lambda x: -sum(v["mat"]+v["mo"] for v in x[1].values())):
        # Sector row
        rows.append([_p(f"  {sector}", _OR_SECTOR), _p("", _OR_SECTOR), _p("", _OR_SECTOR), _p("", _OR_SECTOR)])
        sec_row_idx = len(rows) - 1
        style_cmds.append(("BACKGROUND", (0, sec_row_idx), (-1, sec_row_idx), _C_SECTOR))

        sec_mat = sec_mo = 0.0
        alt_rubro = False
        for rubro, vals in sorted(rubros.items(), key=lambda x: -(x[1]["mat"]+x[1]["mo"])):
            mat = vals.get("mat", 0.0)
            mo  = vals.get("mo",  0.0)
            sec_mat += mat
            sec_mo  += mo
            mat_txt = _fmt_gs(mat) if mat else "---"
            mo_txt  = _fmt_gs(mo)  if mo  else "---"
            tot_txt = _fmt_gs(mat + mo)
            rows.append([
                _p(f"    {rubro}", _OR_RUBRO_RESUMEN),
                _p(mat_txt, _OR_RUBRO_RESUMEN),
                _p(mo_txt,  _OR_RUBRO_RESUMEN),
                _p(tot_txt, _OR_RUBRO_RESUMEN),
            ])
            rubro_row_idx = len(rows) - 1
            row_bg = _C_ALT if alt_rubro else colors.white
            style_cmds.append(("BACKGROUND", (0, rubro_row_idx), (-1, rubro_row_idx), row_bg))
            alt_rubro = not alt_rubro

        total_mat += sec_mat
        total_mo  += sec_mo

    # Total row
    rows.append([
        _p("Total:", _OR_SUB),
        _p(_fmt_gs(total_mat), _OR_SUB),
        _p(_fmt_gs(total_mo),  _OR_SUB),
        _p(_fmt_gs(total_mat + total_mo), _OR_SUB),
    ])
    tot_idx = len(rows) - 1
    style_cmds.append(("BACKGROUND",  (0, tot_idx), (-1, tot_idx), _C_TOTAL))
    style_cmds.append(("LINEABOVE",   (0, tot_idx), (-1, tot_idx), 1.5, _DK))

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle(style_cmds))
    return table


def _build_compras_table(
    compras: list[dict],
    obra_nombre: str,
    available_width: float,
) -> list:
    """Retorna una lista de flowables con tablas jerárquicas de materiales."""
    W = available_width
    col_widths = [W * 0.52, W * 0.10, W * 0.10, W * 0.28]

    flowables = []
    # Agrupar por sector → rubro
    from collections import defaultdict
    by_sector: dict = defaultdict(lambda: defaultdict(list))
    for row in compras:
        if row.get("_obra_clave") == obra_nombre or row.get("_obra_clave", "").startswith(obra_nombre[:8]):
            by_sector[row.get("_sector", "—")][row.get("_rubro", "—")].append(row)

    for sector in sorted(by_sector):
        rubros = by_sector[sector]
        rows = []
        style_cmds = [
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 0), (3, -1), "RIGHT"),
        ]

        # Column header
        rows.append([
            _p("Descripción", _OR_HDR),
            _p("Unidad", _OR_HDR),
            _p("Cant.", _OR_HDR),
            _p("Monto total", _OR_HDR),
        ])
        style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), _C_RUBRO))

        # Obra row
        rows.append([_p(obra_nombre, _OR_OBRA), _p("", _OR_OBRA), _p("", _OR_OBRA), _p("", _OR_OBRA)])
        style_cmds.append(("BACKGROUND", (0, 1), (-1, 1), _C_OBRA))

        # Sector row
        rows.append([_p(f"  {sector}", _OR_SECTOR), _p("", _OR_SECTOR), _p("", _OR_SECTOR), _p("", _OR_SECTOR)])
        style_cmds.append(("BACKGROUND", (0, 2), (-1, 2), _C_SECTOR))

        item_counter = 3
        first_rubro = True
        sector_total = 0.0
        for rubro in sorted(rubros, key=lambda r: -sum(float(it.get("MontoTotal",0) or 0) for it in rubros[r])):
            items = rubros[rubro]
            # White spacer row before non-first rubros
            if not first_rubro:
                rows.append(["", "", "", ""])
                style_cmds.extend([
                    ("BACKGROUND",   (0, item_counter), (-1, item_counter), colors.white),
                    ("TOPPADDING",   (0, item_counter), (-1, item_counter), 3),
                    ("BOTTOMPADDING",(0, item_counter), (-1, item_counter), 3),
                    ("LINEABOVE",    (0, item_counter), (-1, item_counter), 0, colors.white),
                    ("LINEBELOW",    (0, item_counter), (-1, item_counter), 0, colors.white),
                    ("LINEBEFORE",   (0, item_counter), (-1, item_counter), 0, colors.white),
                    ("LINEAFTER",    (0, item_counter), (-1, item_counter), 0, colors.white),
                ])
                item_counter += 1
            # Rubro row
            rows.append([_p(f"    {rubro}", _OR_RUBRO), _p("", _OR_RUBRO), _p("", _OR_RUBRO), _p("", _OR_RUBRO)])
            style_cmds.append(("BACKGROUND", (0, item_counter), (-1, item_counter), _C_RUBRO))
            first_rubro = False
            item_counter += 1

            # Agregar ítems con la misma descripción
            from collections import defaultdict as _dd
            agg_map: dict = {}
            for it in items:
                k = (it.get("Descripcion", "") or "").strip().upper()
                if k in agg_map:
                    agg_map[k]["MontoTotal"] = float(agg_map[k].get("MontoTotal", 0) or 0) + float(it.get("MontoTotal", 0) or 0)
                    try:
                        agg_map[k]["Cantidad"] = float(agg_map[k].get("Cantidad", 0) or 0) + float(it.get("Cantidad", 0) or 0)
                    except (ValueError, TypeError):
                        pass
                else:
                    agg_map[k] = dict(it)
            items = sorted(agg_map.values(), key=lambda x: -float(x.get("MontoTotal",0) or 0))

            rubro_total = 0.0
            alt = False
            for item in items:
                monto = item.get("MontoTotal", 0) or 0
                rubro_total += float(monto)
                cant = item.get("Cantidad", "")
                cant_txt = str(int(cant)) if cant and str(cant) != "" else "1"
                rows.append([
                    _p(item.get("Descripcion", ""), _OR_ITEM),
                    _p(item.get("Unidad", "GL"), _OR_ITEM),
                    _p(cant_txt, _OR_ITEM),
                    _p(_fmt_gs(monto), _OR_ITEM),
                ])
                if alt:
                    style_cmds.append(("BACKGROUND", (0, item_counter), (-1, item_counter), _C_ALT))
                alt = not alt
                item_counter += 1

            # Subtotal rubro
            rows.append([
                _p(f"    {rubro} Total", _OR_SUB),
                _p("", _OR_SUB),
                _p("---", _OR_SUB),
                _p(_fmt_gs(rubro_total), _OR_SUB),
            ])
            style_cmds.append(("BACKGROUND", (0, item_counter), (-1, item_counter), _C_SUB))
            style_cmds.append(("LINEABOVE", (0, item_counter), (-1, item_counter), 0.8, _C_RUBRO))
            sector_total += rubro_total
            item_counter += 1

        # Grand total row
        rows.append([
            _p("Total:", _OR_SUB),
            _p("", _OR_SUB),
            _p("", _OR_SUB),
            _p(_fmt_gs(sector_total), _OR_SUB),
        ])
        style_cmds.append(("BACKGROUND", (0, item_counter), (-1, item_counter), _C_TOTAL))
        style_cmds.append(("LINEABOVE", (0, item_counter), (-1, item_counter), 1.5, _DK))

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle(style_cmds))
        flowables.append(table)
        flowables.append(Spacer(1, 4 * mm))

    return flowables


def _build_pagos_table(
    pagos: list[dict],
    obra_nombre: str,
    available_width: float,
    *,
    show_detail: bool = True,
) -> list:
    """Retorna una lista de flowables con tablas jerárquicas de mano de obra."""
    W = available_width
    col_widths = [W * 0.35, W * 0.18, W * 0.20, W * 0.27]

    flowables = []
    from collections import defaultdict
    by_sector: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in pagos:
        by_sector[row.get("_sector", "—")][row.get("_rubro", "—")][row.get("_trabajador", "—")].append(row)

    def _pt(items): return sum(float(r.get("MontoPago",0) or 0) for r in items)
    def _pr(trabas): return sum(_pt(it) for it in trabas.values())
    def _ps(rubros): return sum(_pr(tr) for tr in rubros.values())

    for sector in sorted(by_sector, key=lambda s: -_ps(by_sector[s])):
        rubros = by_sector[sector]
        rows = []
        style_cmds = [
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ]

        rows.append([
            _p("Trabajador / Fecha", _OR_HDR),
            _p("Concepto", _OR_HDR),
            _p("Método", _OR_HDR),
            _p("Monto Pago", _OR_HDR),
        ])
        style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), _C_RUBRO))

        rows.append([_p(obra_nombre, _OR_OBRA), _p("", _OR_OBRA), _p("", _OR_OBRA), _p("", _OR_OBRA)])
        style_cmds.append(("BACKGROUND", (0, 1), (-1, 1), _C_OBRA))

        rows.append([_p(f"  {sector}", _OR_SECTOR), _p("", _OR_SECTOR), _p("", _OR_SECTOR), _p("", _OR_SECTOR)])
        style_cmds.append(("BACKGROUND", (0, 2), (-1, 2), _C_SECTOR))

        idx = 3
        sector_total = 0.0
        first_rubro = True

        for rubro in sorted(rubros, key=lambda r: -_pr(rubros[r])):
            trabas = rubros[rubro]
            # White spacer row before non-first rubros
            if not first_rubro:
                rows.append(["", "", "", ""])
                style_cmds.extend([
                    ("BACKGROUND",   (0, idx), (-1, idx), colors.white),
                    ("TOPPADDING",   (0, idx), (-1, idx), 3),
                    ("BOTTOMPADDING",(0, idx), (-1, idx), 3),
                    ("LINEABOVE",    (0, idx), (-1, idx), 0, colors.white),
                    ("LINEBELOW",    (0, idx), (-1, idx), 0, colors.white),
                    ("LINEBEFORE",   (0, idx), (-1, idx), 0, colors.white),
                    ("LINEAFTER",    (0, idx), (-1, idx), 0, colors.white),
                ])
                idx += 1
            # Rubro row
            rows.append([_p(f"    {rubro}", _OR_RUBRO), _p("", _OR_RUBRO), _p("", _OR_RUBRO), _p("", _OR_RUBRO)])
            style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), _C_RUBRO))
            first_rubro = False
            idx += 1

            rubro_total = 0.0
            for trab in sorted(trabas, key=lambda t: -_pt(trabas[t])):
                items = trabas[trab]
                trab_total = sum(float(r.get("MontoPago", 0) or 0) for r in items)
                rubro_total += trab_total

                if not show_detail:
                    # Modo colapsado: solo fila de trabajador con total
                    rows.append([
                        _p(f"      {trab}", _OR_ITEM),
                        _p("", _OR_ITEM),
                        _p("", _OR_ITEM),
                        _p(_fmt_gs(trab_total), _OR_ITEM),
                    ])
                    idx += 1
                else:
                    # Modo expandido: trabajador header + filas de pago
                    rows.append([
                        _p(f"      {trab}", _OR_SUB),
                        _p("", _OR_SUB), _p("", _OR_SUB), _p("", _OR_SUB),
                    ])
                    style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), _C_ALT))
                    idx += 1
                    alt = False
                    for r in sorted(items, key=lambda r: -float(r.get("MontoPago",0) or 0)):
                        from datetime import datetime
                        fecha_raw = r.get("FechaPago", "")
                        try:
                            fecha = datetime.strptime(str(fecha_raw)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                        except Exception:
                            fecha = fecha_raw or "—"
                        rows.append([
                            _p(f"        {fecha}", _OR_ITEM),
                            _p(r.get("Concepto", ""), _OR_ITEM),
                            _p(r.get("MetodoPago", ""), _OR_ITEM),
                            _p(_fmt_gs(r.get("MontoPago", 0)), _OR_ITEM),
                        ])
                        if alt:
                            style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), _C_ALT))
                        alt = not alt
                        idx += 1

            # Rubro subtotal
            rows.append([
                _p(f"    {rubro} Total", _OR_SUB),
                _p("", _OR_SUB), _p("", _OR_SUB),
                _p(_fmt_gs(rubro_total), _OR_SUB),
            ])
            style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), _C_SUB))
            style_cmds.append(("LINEABOVE", (0, idx), (-1, idx), 0.8, _C_RUBRO))
            idx += 1
            sector_total += rubro_total

        # Grand total
        rows.append([
            _p("Total:", _OR_SUB),
            _p("", _OR_SUB), _p("", _OR_SUB),
            _p(_fmt_gs(sector_total), _OR_SUB),
        ])
        style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), _C_TOTAL))
        style_cmds.append(("LINEABOVE", (0, idx), (-1, idx), 1.5, _DK))

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle(style_cmds))
        flowables.append(table)
        flowables.append(Spacer(1, 4 * mm))

    return flowables


def generate_obra_report_pdf(
    obra_nombre: str,
    cliente_nombre: str,
    fecha_generacion: str,
    resumen: dict,
    compras: list[dict],
    pagos: list[dict],
    *,
    show_mo_detail: bool = True,
) -> bytes:
    """Genera el reporte completo de obra: resumen + materiales + MO.

    Args:
        obra_nombre: Nombre/clave de la obra (para títulos y filtrado interno).
        cliente_nombre: Nombre del cliente.
        fecha_generacion: Fecha formateada para el header (ej. "27/3/2026").
        resumen: {obra_nombre: {sector: {rubro: {"mat": float, "mo": float}}}}.
        compras: Lista de FactCompra enriquecidas con _obra_clave, _sector, _rubro.
        pagos: Lista de FactPago enriquecidas con _sector, _rubro, _trabajador.

    Returns:
        Bytes del PDF generado.
    """
    buffer = BytesIO()

    subtitle = f"Cliente: {cliente_nombre} | Obra: {obra_nombre}"
    available_width = A4[0] - 50 * mm

    # ── BaseDocTemplate con un PageTemplate por sección ─────────────────────
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30 * mm,
        rightMargin=20 * mm,
        topMargin=30 * mm,
        bottomMargin=20 * mm,
    )

    def _frame(doc):
        return Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")

    def _on_resumen(c, d):
        _obra_page_template(c, d, "RESUMEN GENERAL", subtitle, fecha_generacion)

    def _on_materiales(c, d):
        _obra_page_template(c, d, "DETALLE DE MATERIALES", subtitle, fecha_generacion)

    def _on_mo(c, d):
        _obra_page_template(c, d, "DETALLE DE MANO DE OBRA", subtitle, fecha_generacion)

    doc.addPageTemplates([
        PageTemplate(id="resumen",    frames=[_frame(doc)], onPage=_on_resumen),
        PageTemplate(id="materiales", frames=[_frame(doc)], onPage=_on_materiales),
        PageTemplate(id="mo",         frames=[_frame(doc)], onPage=_on_mo),
    ])

    story: list = []

    # ── Sección 1: Resumen General ──────────────────────────────────────────
    story.append(Spacer(1, 2 * mm))
    story.append(_build_resumen_table(resumen, obra_nombre, available_width))

    # ── Sección 2: Detalle de Materiales ────────────────────────────────────
    story.append(NextPageTemplate("materiales"))
    story.append(PageBreak())
    story.append(Spacer(1, 2 * mm))
    mat_flowables = _build_compras_table(compras, obra_nombre, available_width)
    if mat_flowables:
        story.extend(mat_flowables)
    else:
        story.append(Paragraph("<i>Sin registros de materiales.</i>", _OR_ITEM))

    # ── Sección 3: Detalle de Mano de Obra ──────────────────────────────────
    story.append(NextPageTemplate("mo"))
    story.append(PageBreak())
    story.append(Spacer(1, 2 * mm))
    mo_flowables = _build_pagos_table(pagos, obra_nombre, available_width, show_detail=show_mo_detail)
    if mo_flowables:
        story.extend(mo_flowables)
    else:
        story.append(Paragraph("<i>Sin registros de mano de obra.</i>", _OR_ITEM))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()


def generate_combined_report_pdf(
    title: str,
    sections: list[dict],
    *,
    summary: dict | None = None,
    grand_total: float | None = None,
    grand_total_label: str = "TOTAL GENERAL (Gs.)",
) -> bytes:
    """Genera un PDF con múltiples secciones de tabla, subtotales y total general.

    Args:
        title: Título del reporte.
        sections: Lista de dicts, cada uno con:
            - subtitle: Título de la sección.
            - columns: Lista de dicts (key, label, width_mm, format).
            - rows: Lista de dicts con datos.
            - subtotal: (opcional) float, monto subtotal.
            - subtotal_label: (opcional) str.
        summary: Dict opcional con pares clave-valor para el encabezado.
        grand_total: Monto total general opcional.
        grand_total_label: Label del total general.

    Returns:
        Contenido del PDF como bytes.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30 * mm,
        rightMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
    )

    available_width = A4[0] - 50 * mm
    story: list = []

    story.append(Paragraph(title, _styles["Title"]))
    story.append(Spacer(1, 6 * mm))

    if summary:
        for label, value in summary.items():
            story.append(Paragraph(f"<b>{label}:</b> {value}", _styles["Normal"]))
        story.append(Spacer(1, 4 * mm))

    for section in sections:
        story.append(Paragraph(section["subtitle"], _SECTION_TITLE))

        if section.get("rows"):
            story.append(_build_table(section["columns"], section["rows"], available_width, show_totals=True))
        else:
            story.append(Paragraph("<i>Sin registros</i>", _styles["Normal"]))
            story.append(Spacer(1, 4 * mm))

    if grand_total is not None:
        story.append(Spacer(1, 4 * mm))
        total_data = [
            [
                Paragraph("<b>TOTAL GENERAL</b>", _CELL_BOLD_STYLE),
                Paragraph(_safe(_fmt_guaranies(grand_total)), _CELL_BOLD_STYLE),
            ]
        ]
        total_table = Table(total_data, colWidths=[available_width * 0.7, available_width * 0.3])
        total_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#bfc9ca")),
            ("LINEABOVE", (0, 0), (-1, 0), 2, colors.HexColor("#2c3e50")),
            ("LINEBELOW", (0, 0), (-1, 0), 2, colors.HexColor("#2c3e50")),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(total_table)

    doc.build(story)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Planilla de Medición — Tool 5
# ---------------------------------------------------------------------------

def _dim_fmt(value) -> str:
    """Formatea un valor de dimensión: 3 decimales, sin ceros innecesarios. '—' si es 0/None."""
    try:
        f = float(value)
        if f == 0:
            return "—"
        s = f"{f:.3f}".rstrip("0").rstrip(".")
        return s
    except (TypeError, ValueError):
        return "—"


def _build_medicion_lines_table(
    lineas: list[dict],
    available_width: float,
) -> list:
    """Retorna flowables con tabla jerárquica de medición: Sector → Rubro → ítems."""
    from collections import defaultdict

    W = available_width
    # 55+10+15+15+15+15+17+18 = 160 mm — exacto para A4 con márgenes 30/20
    col_widths_mm = [55, 10, 15, 15, 15, 15, 17, 18]
    col_widths = [w * mm for w in col_widths_mm]
    total_w = sum(col_widths)
    if total_w > W:
        scale = W / total_w
        col_widths = [c * scale for c in col_widths]

    flowables = []
    by_sector: dict = defaultdict(lambda: defaultdict(list))
    for linea in lineas:
        sector = linea.get("_sector_name") or "—"
        rubro = linea.get("_rubro_name") or "—"
        by_sector[sector][rubro].append(linea)

    grand_total = 0.0

    for sector in sorted(by_sector):
        rubros = by_sector[sector]
        rows = []
        style_cmds = [
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN",         (0, 0), (0, -1),  "LEFT"),
        ]

        # Column header
        rows.append([
            _p("Descripción", _OR_HDR),
            _p("Ud.", _OR_HDR),
            _p("Largo", _OR_HDR),
            _p("Ancho", _OR_HDR),
            _p("Alto", _OR_HDR),
            _p("Cant.", _OR_HDR),
            _p("P.U. (Gs.)", _OR_HDR),
            _p("Total (Gs.)", _OR_HDR),
        ])
        style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), _C_RUBRO))

        # Sector row
        rows.append([_p(f"  {sector}", _OR_SECTOR)] + [_p("", _OR_SECTOR)] * 7)
        style_cmds.append(("BACKGROUND", (0, 1), (-1, 1), _C_SECTOR))

        row_idx = 2
        sector_total = 0.0

        for rubro in sorted(rubros):
            items = rubros[rubro]

            # Rubro row
            rows.append([_p(f"    {rubro}", _OR_RUBRO)] + [_p("", _OR_RUBRO)] * 7)
            style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _C_RUBRO))
            row_idx += 1

            rubro_total = 0.0
            alt = False
            for item in items:
                cant = float(item.get("Cantidad") or 0)
                pu = float(item.get("PrecioUnitario") or 0)
                total = cant * pu
                rubro_total += total

                pu_txt = _fmt_guaranies(pu) if pu else "S/P"
                total_txt = _fmt_guaranies(total) if pu else "S/P"

                rows.append([
                    _p(item.get("Descripcion", ""), _OR_ITEM),
                    _p(item.get("Unidad", ""), _OR_ITEM),
                    _p(_dim_fmt(item.get("Largo")), _OR_ITEM),
                    _p(_dim_fmt(item.get("Ancho")), _OR_ITEM),
                    _p(_dim_fmt(item.get("Alto")), _OR_ITEM),
                    _p(_dim_fmt(item.get("Cantidad")), _OR_ITEM),
                    _p(pu_txt, _OR_ITEM),
                    _p(total_txt, _OR_ITEM),
                ])
                if alt:
                    style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _C_ALT))
                alt = not alt
                row_idx += 1

            # Rubro subtotal
            rows.append([
                _p(f"    Subtotal {rubro}", _OR_SUB),
                _p("", _OR_SUB), _p("", _OR_SUB), _p("", _OR_SUB),
                _p("", _OR_SUB), _p("", _OR_SUB), _p("", _OR_SUB),
                _p(_fmt_guaranies(rubro_total), _OR_SUB),
            ])
            style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _C_SUB))
            style_cmds.append(("LINEABOVE",   (0, row_idx), (-1, row_idx), 0.8, _C_RUBRO))
            sector_total += rubro_total
            row_idx += 1

        grand_total += sector_total

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle(style_cmds))
        flowables.append(table)
        flowables.append(Spacer(1, 4 * mm))

    # Grand total (separate table for emphasis)
    if flowables:
        gt_rows = [[_p("TOTAL GENERAL", _OR_SUB), _p(_fmt_guaranies(grand_total), _OR_SUB)]]
        gt_table = Table(gt_rows, colWidths=[W * 0.70, W * 0.30])
        gt_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), _C_TOTAL),
            ("LINEABOVE",     (0, 0), (-1, 0), 1.5, _DK),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("ALIGN",         (1, 0), (1, 0), "RIGHT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        flowables.append(gt_table)

    return flowables


def generate_medicion_pdf(
    obra_nombre: str,
    subcontratista_nombre: str,
    fecha_medicion: str,
    observaciones: str,
    lineas: list[dict],
    fecha_generacion: str,
) -> bytes:
    """Genera la planilla de medición en PDF.

    Args:
        obra_nombre: Nombre/clave de la obra.
        subcontratista_nombre: Nombre del subcontratista.
        fecha_medicion: Fecha de la medición formateada (ej. "28/03/2026").
        observaciones: Observaciones opcionales (cadena vacía si no hay).
        lineas: Lista de dicts con _sector_name, _rubro_name, Descripcion, Unidad,
                Largo, Ancho, Alto, Cantidad, PrecioUnitario.
        fecha_generacion: Fecha de generación del PDF (ej. "28/3/2026").

    Returns:
        Bytes del PDF generado.
    """
    buffer = BytesIO()
    available_width = A4[0] - 50 * mm
    subtitle = (
        f"Obra: {obra_nombre}  |  Subcontratista: {subcontratista_nombre}"
        f"  |  Fecha: {fecha_medicion}"
    )

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30 * mm,
        rightMargin=20 * mm,
        topMargin=30 * mm,
        bottomMargin=20 * mm,
    )

    def _frame(d):
        return Frame(d.leftMargin, d.bottomMargin, d.width, d.height, id="normal")

    def _on_page(c, d):
        _obra_page_template(c, d, "PLANILLA DE MEDICIÓN", subtitle, fecha_generacion)

    doc.addPageTemplates([PageTemplate(id="medicion", frames=[_frame(doc)], onPage=_on_page)])

    story: list = [Spacer(1, 2 * mm)]

    # Header info block
    info_data = [
        [Paragraph("<b>Obra:</b>", _OR_ITEM),              _p(_safe(obra_nombre), _OR_ITEM)],
        [Paragraph("<b>Subcontratista:</b>", _OR_ITEM),    _p(_safe(subcontratista_nombre), _OR_ITEM)],
        [Paragraph("<b>Fecha de medición:</b>", _OR_ITEM), _p(_safe(fecha_medicion), _OR_ITEM)],
    ]
    if observaciones:
        info_data.append([Paragraph("<b>Observaciones:</b>", _OR_ITEM), _p(_safe(observaciones), _OR_ITEM)])

    info_table = Table(info_data, colWidths=[45 * mm, available_width - 45 * mm])
    info_table.setStyle(TableStyle([
        ("TOPPADDING",     (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 2),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _C_ALT]),
        ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 4 * mm))

    # Measurement lines
    if lineas:
        story.extend(_build_medicion_lines_table(lineas, available_width))
    else:
        story.append(Paragraph("<i>Sin líneas de medición.</i>", _OR_ITEM))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Acumulado de Mediciones — Tool 5 vista general
# ---------------------------------------------------------------------------

def _build_acumulado_table(items: list[dict], available_width: float) -> list:
    """Flowables jerárquicos por Rubro para el acumulado de mediciones.

    items: cada dict tiene _rubro_name, Descripcion, Unidad,
           CantidadTotal, PUUltimo, TotalAcumulado.
    """
    from collections import defaultdict

    W = available_width
    # Desc(75) Ud(12) Cant(20) PU(25) Total(28) = 160mm
    col_widths = [w * mm for w in [75, 12, 20, 25, 28]]
    total_w = sum(col_widths)
    if total_w > W:
        scale = W / total_w
        col_widths = [c * scale for c in col_widths]

    flowables = []
    by_rubro: dict = defaultdict(list)
    for item in items:
        by_rubro[item.get("_rubro_name", "—")].append(item)

    grand_total = 0.0

    for rubro in sorted(by_rubro):
        rubro_items = by_rubro[rubro]
        rows = []
        style_cmds = [
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN",         (0, 0), (0, -1),  "LEFT"),
        ]

        # Column header
        rows.append([
            _p("Descripción", _OR_HDR),
            _p("Ud.", _OR_HDR),
            _p("Cant. Total", _OR_HDR),
            _p("P.U. Último (Gs.)", _OR_HDR),
            _p("Total Acum. (Gs.)", _OR_HDR),
        ])
        style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), _C_RUBRO))

        # Rubro row
        rows.append([_p(f"  {rubro}", _OR_RUBRO)] + [_p("", _OR_RUBRO)] * 4)
        style_cmds.append(("BACKGROUND", (0, 1), (-1, 1), _C_RUBRO))

        row_idx = 2
        rubro_total = 0.0
        alt = False

        for item in rubro_items:
            cant  = float(item.get("CantidadTotal") or 0)
            pu    = float(item.get("PUUltimo") or 0)
            total = float(item.get("TotalAcumulado") or 0)
            rubro_total += total

            rows.append([
                _p(item.get("Descripcion", ""), _OR_ITEM),
                _p(item.get("Unidad", ""), _OR_ITEM),
                _p(_dim_fmt(cant), _OR_ITEM),
                _p(_fmt_guaranies(pu) if pu else "S/P", _OR_ITEM),
                _p(_fmt_guaranies(total) if pu else "S/P", _OR_ITEM),
            ])
            if alt:
                style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _C_ALT))
            alt = not alt
            row_idx += 1

        # Rubro subtotal
        rows.append([
            _p(f"  Subtotal {rubro}", _OR_SUB),
            _p("", _OR_SUB), _p("", _OR_SUB), _p("", _OR_SUB),
            _p(_fmt_guaranies(rubro_total), _OR_SUB),
        ])
        style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _C_SUB))
        style_cmds.append(("LINEABOVE",   (0, row_idx), (-1, row_idx), 0.8, _C_RUBRO))
        grand_total += rubro_total

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle(style_cmds))
        flowables.append(table)
        flowables.append(Spacer(1, 4 * mm))

    # Grand total
    if flowables:
        gt_rows = [[_p("TOTAL ACUMULADO", _OR_SUB), _p(_fmt_guaranies(grand_total), _OR_SUB)]]
        gt_table = Table(gt_rows, colWidths=[W * 0.70, W * 0.30])
        gt_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), _C_TOTAL),
            ("LINEABOVE",     (0, 0), (-1, 0), 1.5, _DK),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("ALIGN",         (1, 0), (1, 0), "RIGHT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        flowables.append(gt_table)

    return flowables


def generate_acumulado_pdf(
    obra_nombre: str,
    subcontratista_nombre: str,
    periodo: str,
    n_planillas: int,
    items: list[dict],
    fecha_generacion: str,
) -> bytes:
    """Genera el acumulado de mediciones en PDF.

    Args:
        obra_nombre: Nombre/clave de la obra (o "Todas las obras").
        subcontratista_nombre: Nombre del subcontratista (o "Todos").
        periodo: String del período, ej. "01/01/2026 – 28/03/2026".
        n_planillas: Cantidad de planillas incluidas.
        items: Lista de ítems agregados con _rubro_name, Descripcion, Unidad,
               CantidadTotal, PUUltimo, TotalAcumulado.
        fecha_generacion: Fecha formateada para el header.

    Returns:
        Bytes del PDF generado.
    """
    buffer = BytesIO()
    available_width = A4[0] - 50 * mm
    subtitle = (
        f"Obra: {obra_nombre}  |  Subcontratista: {subcontratista_nombre}"
        f"  |  Período: {periodo}"
    )

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30 * mm,
        rightMargin=20 * mm,
        topMargin=30 * mm,
        bottomMargin=20 * mm,
    )

    def _frame(d):
        return Frame(d.leftMargin, d.bottomMargin, d.width, d.height, id="normal")

    def _on_page(c, d):
        _obra_page_template(c, d, "ACUMULADO DE MEDICIONES", subtitle, fecha_generacion)

    doc.addPageTemplates([PageTemplate(id="acumulado", frames=[_frame(doc)], onPage=_on_page)])

    story: list = [Spacer(1, 2 * mm)]

    info_data = [
        [Paragraph("<b>Obra:</b>", _OR_ITEM),               _p(_safe(obra_nombre), _OR_ITEM)],
        [Paragraph("<b>Subcontratista:</b>", _OR_ITEM),      _p(_safe(subcontratista_nombre), _OR_ITEM)],
        [Paragraph("<b>Período:</b>", _OR_ITEM),              _p(_safe(periodo), _OR_ITEM)],
        [Paragraph("<b>Planillas incluidas:</b>", _OR_ITEM),  _p(str(n_planillas), _OR_ITEM)],
    ]
    info_table = Table(info_data, colWidths=[45 * mm, available_width - 45 * mm])
    info_table.setStyle(TableStyle([
        ("TOPPADDING",     (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 2),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _C_ALT]),
        ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 4 * mm))

    if items:
        story.extend(_build_acumulado_table(items, available_width))
    else:
        story.append(Paragraph("<i>Sin ítems para mostrar.</i>", _OR_ITEM))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Certificado de Obra — memo PDF (portrait, summary style)
# ---------------------------------------------------------------------------

def _guaranies_en_letras(monto: int) -> str:
    """Convierte un monto entero en guaraníes a texto en español."""
    if monto == 0:
        return "CERO"

    unidades = [
        "", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE",
        "OCHO", "NUEVE", "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE",
        "QUINCE", "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE",
        "VEINTE",
    ]
    decenas = [
        "", "", "VEINTI", "TREINTA", "CUARENTA", "CINCUENTA",
        "SESENTA", "SETENTA", "OCHENTA", "NOVENTA",
    ]
    centenas = [
        "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS",
        "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS",
        "NOVECIENTOS",
    ]

    def _num_a_letras_grupo(n: int) -> str:
        if n == 0:
            return ""
        if n == 100:
            return "CIEN"
        partes = []
        c = n // 100
        r = n % 100
        if c:
            partes.append(centenas[c])
        if r <= 20:
            if r:
                partes.append(unidades[r])
        elif r < 30:
            partes.append("VEINTI" + unidades[r - 20].lower() if r > 20 else "VEINTE")
        else:
            d = r // 10
            u = r % 10
            partes.append(decenas[d])
            if u:
                partes.append("Y " + unidades[u])
        return " ".join(partes)

    if monto < 0:
        return "MENOS " + _guaranies_en_letras(-monto)

    partes = []
    # Billions
    billones = monto // 1_000_000_000
    monto %= 1_000_000_000
    if billones:
        if billones == 1:
            partes.append("UN MIL")
        else:
            partes.append(_num_a_letras_grupo(billones) + " MIL")

    # Millions
    millones = monto // 1_000_000
    monto %= 1_000_000
    if millones:
        if millones == 1:
            partes.append("UN MILLÓN")
        else:
            partes.append(_num_a_letras_grupo(millones) + " MILLONES")

    # Thousands
    miles = monto // 1_000
    monto %= 1_000
    if miles:
        if miles == 1:
            partes.append("MIL")
        else:
            partes.append(_num_a_letras_grupo(miles) + " MIL")

    # Units
    if monto:
        partes.append(_num_a_letras_grupo(monto))

    return " ".join(partes)


def generate_certificado_memo_pdf(
    profesional_nombre: str,
    destinatarios: str,
    titulo_medicion: str,
    fecha: str,
    obras_data: list[dict],
    fecha_generacion: str,
) -> bytes:
    """Genera el PDF resumen tipo memo de certificado de obra.

    Args:
        profesional_nombre: "De:" (ej. "Arq. José María Sanchez").
        destinatarios: "A:" (nombres separados por coma).
        titulo_medicion: "CERTIFICADO DE OBRA\\n(2° MEDICIÓN)".
        fecha: Fecha del certificado (ej. "30/08/2025").
        obras_data: Lista de dicts, cada uno con:
            - obra_nombre: str
            - superficie: str (ej. "684 M2")
            - pct_avance: float
            - items: list[dict] con ItemNro, Rubro, PctActual, MontoActual
            - total: float
        fecha_generacion: Fecha de generación.

    Returns:
        Bytes del PDF.
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30 * mm,
        rightMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
    )
    available_width = A4[0] - 50 * mm

    _memo_item = ParagraphStyle("MemoItem", parent=_styles["Normal"], fontSize=9, leading=12)
    _memo_title = ParagraphStyle("MemoTitle", parent=_styles["Normal"], fontSize=14, leading=18,
                                 fontName="Helvetica-Bold", alignment=1)
    _memo_subtitle = ParagraphStyle("MemoSub", parent=_styles["Normal"], fontSize=11, leading=14,
                                    fontName="Helvetica-Bold", alignment=1)
    _memo_hdr = ParagraphStyle("MemoHdr", parent=_styles["Normal"], fontSize=8, leading=10,
                               fontName="Helvetica-Bold", textColor=_WH)
    _memo_cell = ParagraphStyle("MemoCell", parent=_styles["Normal"], fontSize=8, leading=10)
    _memo_cell_r = ParagraphStyle("MemoCellR", parent=_styles["Normal"], fontSize=8, leading=10,
                                  alignment=2)

    story: list = []

    # Memo header
    story.append(Paragraph(f"<b>Memo:</b> Medición de obras.", _memo_item))
    story.append(Paragraph(f"<b>De:</b> {_safe(profesional_nombre)}.", _memo_item))
    if destinatarios:
        story.append(Paragraph(f"<b>A:</b> {_safe(destinatarios)}.", _memo_item))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Por la presente remito medición de obras en curso.",
        _memo_item,
    ))
    story.append(Paragraph("Saludos cordiales.", _memo_item))
    story.append(Spacer(1, 6 * mm))

    # Title
    for line in titulo_medicion.split("\n"):
        story.append(Paragraph(_safe(line), _memo_title if "CERTIFICADO" in line else _memo_subtitle))
    story.append(Spacer(1, 2 * mm))

    # Date (right-aligned)
    _memo_right = ParagraphStyle("MemoRight", parent=_styles["Normal"], fontSize=9, alignment=2,
                                 fontName="Helvetica-Bold")
    story.append(Paragraph(f"FECHA: {_safe(fecha)}", _memo_right))
    story.append(Spacer(1, 4 * mm))

    # Per-obra sections
    grand_total = 0
    for idx, od in enumerate(obras_data):
        obra_label = od["obra_nombre"]
        superficie = od.get("superficie", "")
        pct        = od.get("pct_avance", 0)
        items      = od.get("items", [])
        total      = od.get("total", 0)

        suffix = f" ({superficie})" if superficie else ""
        letra  = chr(65 + idx)

        # Section header
        obra_hdr_style = ParagraphStyle("ObraHdr", parent=_styles["Normal"], fontSize=10,
                                        fontName="Helvetica-Bold")
        pct_style = ParagraphStyle("PctStyle", parent=_styles["Normal"], fontSize=10,
                                   fontName="Helvetica-Bold", alignment=2)
        hdr_data = [[
            Paragraph(f"{letra}) OBRA - {_safe(obra_label.upper())}{_safe(suffix)}", obra_hdr_style),
            Paragraph(f"{pct:.2f}%", pct_style),
        ]]
        hdr_table = Table(hdr_data, colWidths=[available_width * 0.75, available_width * 0.25])
        hdr_table.setStyle(TableStyle([
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(hdr_table)
        story.append(Spacer(1, 2 * mm))

        # Items table
        if items:
            col_widths = [15 * mm, available_width - 75 * mm, 15 * mm, 45 * mm]
            table_data = [[
                Paragraph("Item", _memo_hdr),
                Paragraph("Rubro", _memo_hdr),
                Paragraph("%", _memo_hdr),
                Paragraph("Precio Total", _memo_hdr),
            ]]
            for item in items:
                table_data.append([
                    Paragraph(_safe(item.get("ItemNro", "")), _memo_cell),
                    Paragraph(_safe(item.get("Rubro", "")), _memo_cell),
                    Paragraph(f"{item.get('PctActual', 0):.0f}%", _memo_cell_r),
                    Paragraph(_fmt_guaranies(item.get("MontoActual", 0)), _memo_cell_r),
                ])

            # Subtotal row
            table_data.append([
                Paragraph("TOTAL GS", _memo_cell),
                Paragraph("", _memo_cell),
                Paragraph("", _memo_cell),
                Paragraph(_fmt_guaranies(total), _memo_cell_r),
            ])

            t = Table(table_data, colWidths=col_widths, repeatRows=1)
            style_cmds = [
                ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#2e4053")),
                ("TEXTCOLOR",     (0, 0), (-1, 0), _WH),
                ("TOPPADDING",    (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING",   (0, 0), (-1, -1), 4),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
                ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                # Subtotal row
                ("BACKGROUND",    (0, -1), (-1, -1), _C_SUB),
                ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
            # Alternating rows
            for r in range(1, len(table_data) - 1):
                if r % 2 == 0:
                    style_cmds.append(("BACKGROUND", (0, r), (-1, r), _C_ALT))
            t.setStyle(TableStyle(style_cmds))
            story.append(t)

        # "Son Guaraníes"
        story.append(Spacer(1, 1 * mm))
        letras = _guaranies_en_letras(int(total))
        story.append(Paragraph(f"<b>Son Guaraníes:</b> {_safe(letras)}", _memo_cell))
        story.append(Spacer(1, 6 * mm))

        grand_total += total

    # Grand total
    story.append(Spacer(1, 2 * mm))
    gt_data = [[
        Paragraph("<b>TOTAL GS CERTIFICADO DE OBRA</b>", _memo_cell),
        Paragraph(f"<b>{_fmt_guaranies(grand_total)}</b>", _memo_cell_r),
    ]]
    gt_table = Table(gt_data, colWidths=[available_width * 0.65, available_width * 0.35])
    gt_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(gt_table)

    letras_total = _guaranies_en_letras(int(grand_total))
    story.append(Paragraph(
        f"<b>Son Guaraníes:</b> {_safe(letras_total)}",
        _memo_cell,
    ))

    # Signature
    story.append(Spacer(1, 25 * mm))
    _sig_style = ParagraphStyle("SigStyle", parent=_styles["Normal"], fontSize=9, alignment=2)
    story.append(Paragraph("………….…………………...………", _sig_style))
    story.append(Paragraph(f"<b>{_safe(profesional_nombre)}</b>", _sig_style))

    doc.build(story)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Certificado de Obra — planilla detallada (landscape)
# ---------------------------------------------------------------------------

_CERT_ITEM = ParagraphStyle("CertItem", parent=_styles["Normal"], fontSize=5.5, leading=7)
_CERT_ITEM_R = ParagraphStyle("CertItemR", parent=_styles["Normal"], fontSize=5.5, leading=7, alignment=2)
_CERT_HDR = ParagraphStyle("CertHdr", parent=_styles["Normal"], fontSize=5.5, leading=7,
                           fontName="Helvetica-Bold", textColor=_WH)
_CERT_GRP = ParagraphStyle("CertGrp", parent=_styles["Normal"], fontSize=6, leading=7.5,
                           fontName="Helvetica-Bold", textColor=_WH)
_CERT_ZONA = ParagraphStyle("CertZona", parent=_styles["Normal"], fontSize=6.5, leading=8,
                            fontName="Helvetica-Bold", textColor=_WH)
_CERT_BOLD = ParagraphStyle("CertBold", parent=_styles["Normal"], fontSize=5.5, leading=7,
                            fontName="Helvetica-Bold")
_CERT_BOLD_R = ParagraphStyle("CertBoldR", parent=_styles["Normal"], fontSize=5.5, leading=7,
                              fontName="Helvetica-Bold", alignment=2)


def _cert_page_template_landscape(canvas_obj, doc, title: str, subtitle: str, fecha: str):
    """Header for landscape certificate detail pages."""
    canvas_obj.saveState()
    page_w, page_h = A4[1], A4[0]  # landscape dimensions

    top = page_h

    if _LOGO_PATH.exists():
        canvas_obj.drawImage(
            str(_LOGO_PATH),
            20 * mm, top - 16 * mm,
            width=24 * mm, height=9 * mm,
            preserveAspectRatio=True, mask="auto",
        )

    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.setFillColor(_DK)
    canvas_obj.drawCentredString(page_w / 2, top - 12 * mm, title)

    canvas_obj.setFont("Helvetica-Bold", 7)
    canvas_obj.drawRightString(page_w - 15 * mm, top - 10 * mm, f"Generado: {fecha}")

    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.setFillColor(colors.HexColor("#5d6d7e"))
    canvas_obj.drawCentredString(page_w / 2, top - 17 * mm, subtitle)

    canvas_obj.setStrokeColor(colors.HexColor("#E8622A"))
    canvas_obj.setLineWidth(1.0)
    canvas_obj.line(20 * mm, top - 19 * mm, page_w - 15 * mm, top - 19 * mm)

    canvas_obj.restoreState()


class _NumberedCanvasLandscape(rl_canvas.Canvas):
    """Canvas with page numbers for landscape pages."""

    def __init__(self, *args, **kwargs):
        rl_canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)

    def _draw_page_number(self, total: int):
        self.setFont("Helvetica", 6)
        self.setFillColor(colors.HexColor("#6B7280"))
        self.drawCentredString(A4[1] / 2, 8 * mm, f"Página {self._pageNumber} de {total}")


def generate_certificado_detalle_pdf(
    obra_nombre: str,
    ubicacion: str,
    propietario: str,
    profesional: str,
    superficie: str,
    cert_numero: int,
    fecha_presupuesto: str,
    fecha_certificado: str,
    display_rows: list[dict],
    fecha_generacion: str,
) -> bytes:
    """Genera la planilla detallada de certificación en landscape.

    Args:
        obra_nombre: Nombre de la obra.
        ubicacion: Ubicación (ej. "Franco").
        propietario: Nombre del propietario/cliente.
        profesional: Nombre del profesional.
        superficie: Superficie (ej. "684 M2").
        cert_numero: Número de certificación.
        fecha_presupuesto: Fecha del presupuesto original.
        fecha_certificado: Fecha de este certificado.
        display_rows: Lista de dicts con todos los campos calculados.
        fecha_generacion: Fecha de generación del PDF.

    Returns:
        Bytes del PDF.
    """
    buffer = BytesIO()
    page_w, page_h = A4[1], A4[0]  # landscape

    suffix = f" ({superficie})" if superficie else ""
    subtitle = f"Obra: {obra_nombre}{suffix}  |  Propietario: {propietario}  |  Profesional: {profesional}"

    doc = BaseDocTemplate(
        buffer,
        pagesize=(page_w, page_h),
        leftMargin=15 * mm,
        rightMargin=10 * mm,
        topMargin=24 * mm,
        bottomMargin=14 * mm,
    )

    available_width = page_w - 25 * mm

    def _frame(d):
        return Frame(d.leftMargin, d.bottomMargin, d.width, d.height, id="normal")

    def _on_page(c, d):
        _cert_page_template_landscape(
            c, d,
            f"PLANILLA DE PRESUPUESTO / CERTIFICADO Nº {cert_numero}",
            subtitle,
            fecha_generacion,
        )

    doc.addPageTemplates([PageTemplate(id="cert_det", frames=[_frame(doc)], onPage=_on_page)])

    story: list = [Spacer(1, 2 * mm)]

    # Metadata block
    meta_data = []
    if ubicacion:
        meta_data.append([
            Paragraph("<b>UBICACIÓN:</b>", _CERT_ITEM),
            Paragraph(_safe(ubicacion), _CERT_ITEM),
            Paragraph("<b>FECHA CERTIFICADO:</b>", _CERT_ITEM),
            Paragraph(_safe(fecha_certificado), _CERT_ITEM),
        ])
    meta_data.append([
        Paragraph("<b>PROPIETARIO:</b>", _CERT_ITEM),
        Paragraph(_safe(propietario), _CERT_ITEM),
        Paragraph("<b>PROFESIONAL:</b>", _CERT_ITEM),
        Paragraph(_safe(profesional), _CERT_ITEM),
    ])
    if meta_data:
        mt = Table(meta_data, colWidths=[30 * mm, available_width / 2 - 30 * mm,
                                          35 * mm, available_width / 2 - 35 * mm])
        mt.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ]))
        story.append(mt)
        story.append(Spacer(1, 3 * mm))

    # Column widths (total ≈ available_width)
    col_w = [
        10 * mm, 52 * mm, 8 * mm, 13 * mm, 16 * mm, 18 * mm,
        13 * mm, 13 * mm, 13 * mm,
        16 * mm, 16 * mm, 16 * mm,
        10 * mm, 10 * mm, 10 * mm,
    ]
    total_w = sum(col_w)
    if total_w != available_width:
        factor = available_width / total_w
        col_w = [w * factor for w in col_w]

    # Two-level header
    hdr0 = [
        Paragraph("<b>PLANILLA DE PRESUPUESTO</b>", _CERT_HDR),
        "", "", "", "", "",
        Paragraph(f"<b>PLANILLA DE CERTIFICADO Nº {cert_numero}</b>", _CERT_HDR),
        "", "", "", "", "",
        Paragraph("<b>% Ejecutado</b>", _CERT_HDR),
        "", "",
    ]
    hdr1 = [
        Paragraph("Item", _CERT_HDR),
        Paragraph("Rubro", _CERT_HDR),
        Paragraph("Unid.", _CERT_HDR),
        Paragraph("Cant.", _CERT_HDR),
        Paragraph("P. Unitario", _CERT_HDR),
        Paragraph("P. Total", _CERT_HDR),
        Paragraph("Cant.Ant.", _CERT_HDR),
        Paragraph("Cant.Actual", _CERT_HDR),
        Paragraph("Cant.Acum.", _CERT_HDR),
        Paragraph("Anterior", _CERT_HDR),
        Paragraph("Actual", _CERT_HDR),
        Paragraph("Acumulado", _CERT_HDR),
        Paragraph("Anterior", _CERT_HDR),
        Paragraph("Actual", _CERT_HDR),
        Paragraph("% Acum.", _CERT_HDR),
    ]

    table_data = [hdr0, hdr1]

    # Data rows
    current_zona = ""
    current_grupo = ""
    for r in display_rows:
        zona = r.get("Zona", "") or ""
        grupo = r.get("GrupoNombre", "") or ""

        if zona and zona != current_zona:
            current_zona = zona
            current_grupo = ""  # reset grupo al cambiar de zona
            zona_row = type("_TaggedRow", (list,), {"__meta__": "zona"})(
                [Paragraph(f"<b>{_safe(zona).upper()}</b>", _CERT_ZONA)] + [""] * 14
            )
            table_data.append(zona_row)

        if grupo and grupo != current_grupo:
            current_grupo = grupo
            grp_row = type("_TaggedRow", (list,), {"__meta__": "grupo"})(
                [Paragraph(f"<b>{_safe(grupo)}:</b>", _CERT_GRP)] + [""] * 14
            )
            table_data.append(grp_row)

        sin_cotizar = r.get("SinCotizar", False)
        style = _CERT_ITEM if not sin_cotizar else ParagraphStyle(
            "CertGray", parent=_CERT_ITEM, textColor=colors.HexColor("#999999"),
        )
        style_r = _CERT_ITEM_R if not sin_cotizar else ParagraphStyle(
            "CertGrayR", parent=_CERT_ITEM_R, textColor=colors.HexColor("#999999"),
        )

        def _pn(val, fmt=",.0f"):
            try:
                return Paragraph(_safe(f"{float(val):{fmt}}".replace(",", ".")), style_r)
            except (ValueError, TypeError):
                return Paragraph("", style_r)

        def _pp(val):
            try:
                return Paragraph(f"{float(val):.2f}%", style_r)
            except (ValueError, TypeError):
                return Paragraph("0,00%", style_r)

        rubro_text = _safe(r["Rubro"])
        if sin_cotizar:
            rubro_text = f"<i>{rubro_text}</i>"
        obs = r.get("Observaciones", "")
        if obs and not sin_cotizar:
            rubro_text += f" <i>({_safe(obs)})</i>"

        data_row = [
            Paragraph(_safe(r["ItemNro"]), style),
            Paragraph(rubro_text, style),
            Paragraph(_safe(r["Unidad"]), style),
            _pn(r["CantPres"], ",.3f") if r["CantPres"] else Paragraph("", style),
            _pn(r["PU"]) if r["PU"] else Paragraph("", style),
            _pn(r["PTotal"]) if r["PTotal"] else Paragraph("", style),
            _pn(r["CantAnt"], ",.2f") if r["CantAnt"] else Paragraph("", style),
            _pn(r["CantActual"], ",.2f") if r["CantActual"] else Paragraph("", style),
            _pn(r["CantAcum"], ",.2f") if r["CantAcum"] else Paragraph("", style),
            _pn(r["MontoAnt"]) if r["MontoAnt"] else Paragraph("0", style_r),
            _pn(r["MontoActual"]) if r["MontoActual"] else Paragraph("0", style_r),
            _pn(r["MontoAcum"]) if r["MontoAcum"] else Paragraph("0", style_r),
            _pp(r["PctAnt"]),
            _pp(r["PctActual"]),
            _pp(r["PctAcum"]),
        ]
        table_data.append(data_row)

    # Totals row
    total_pres  = sum(r["PTotal"] for r in display_rows)
    total_m_ant = sum(r["MontoAnt"] for r in display_rows)
    total_m_act = sum(r["MontoActual"] for r in display_rows)
    total_m_acu = sum(r["MontoAcum"] for r in display_rows)
    pct_ant_t   = (total_m_ant / total_pres * 100) if total_pres else 0
    pct_act_t   = (total_m_act / total_pres * 100) if total_pres else 0
    pct_acu_t   = (total_m_acu / total_pres * 100) if total_pres else 0

    def _pb(val, fmt=",.0f"):
        return Paragraph(f"<b>{_safe(f'{float(val):{fmt}}'.replace(',', '.'))}</b>", _CERT_BOLD_R)

    totals_row = [
        Paragraph("<b>TOTAL GS SIN IVA</b>", _CERT_BOLD), "", "", "", "",
        _pb(total_pres),
        "", "", "",
        _pb(total_m_ant), _pb(total_m_act), _pb(total_m_acu),
        Paragraph(f"<b>{pct_ant_t:.2f}%</b>", _CERT_BOLD_R),
        Paragraph(f"<b>{pct_act_t:.2f}%</b>", _CERT_BOLD_R),
        Paragraph(f"<b>{pct_acu_t:.2f}%</b>", _CERT_BOLD_R),
    ]
    table_data.append(totals_row)

    # Build table
    table = Table(table_data, colWidths=col_w, repeatRows=2)
    style_cmds = [
        # Header row 0
        ("BACKGROUND",    (0, 0), (5, 0), colors.HexColor("#2e4053")),
        ("BACKGROUND",    (6, 0), (11, 0), colors.HexColor("#1a252f")),
        ("BACKGROUND",    (12, 0), (-1, 0), colors.HexColor("#5d6d7e")),
        ("SPAN",          (0, 0), (5, 0)),
        ("SPAN",          (6, 0), (11, 0)),
        ("SPAN",          (12, 0), (14, 0)),
        # Header row 1
        ("BACKGROUND",    (0, 1), (-1, 1), colors.HexColor("#2e4053")),
        # General
        ("TEXTCOLOR",     (0, 0), (-1, 1), _WH),
        ("TOPPADDING",    (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, 1), "CENTER"),
        # Totals row
        ("BACKGROUND",    (0, -1), (-1, -1), _C_SUB),
        ("SPAN",          (0, -1), (4, -1)),
        ("LINEABOVE",     (0, -1), (-1, -1), 1, colors.HexColor("#1a252f")),
    ]

    # Alternating row colors, zona rows and group rows
    _C_ZONA = colors.HexColor("#E8622A")
    for i in range(2, len(table_data) - 1):
        row = table_data[i]
        if hasattr(row, "__meta__") and row.__meta__ == "zona":
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), _C_ZONA))
            style_cmds.append(("SPAN", (0, i), (-1, i)))
            style_cmds.append(("TEXTCOLOR", (0, i), (-1, i), _WH))
        elif hasattr(row, "__meta__") and row.__meta__ == "grupo":
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), _C_RUBRO))
            style_cmds.append(("SPAN", (0, i), (-1, i)))
        elif i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), _C_ALT))

    table.setStyle(TableStyle(style_cmds))
    story.append(table)

    doc.build(story, canvasmaker=_NumberedCanvasLandscape)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Resumen financiero por obra
# ---------------------------------------------------------------------------

_C_RESUMEN_HDR   = colors.HexColor("#2c3e50")
_C_RESUMEN_PRES  = colors.HexColor("#1a5276")   # azul oscuro — fila presupuesto
_C_RESUMEN_CERT  = colors.HexColor("#1e8449")   # verde — fila certificación
_C_RESUMEN_COB   = colors.HexColor("#784212")   # marrón/naranja — fila cobro
_C_RESUMEN_ALT   = colors.HexColor("#f2f3f4")
_C_RESUMEN_TOTAL = colors.HexColor("#d5d8dc")


def generate_resumen_financiero_pdf(
    obra_nombre: str,
    cliente: str,
    fecha_generacion: str,
    total_presupuesto: float,
    total_certificado: float,
    total_cobrado: float,
    saldo_pendiente: float,
    balance: float,
    timeline: list[dict],
) -> bytes:
    """PDF de resumen financiero por obra: métricas + timeline de movimientos.

    Args:
        obra_nombre:       Nombre/clave de la obra.
        cliente:           Nombre del cliente.
        fecha_generacion:  Fecha de generación (dd/mm/yy).
        total_presupuesto: Monto total del presupuesto.
        total_certificado: Monto total certificado (Confirmado).
        total_cobrado:     Monto total cobrado (MontoRecibido).
        saldo_pendiente:   total_presupuesto - total_cobrado.
        balance:           total_cobrado - total_certificado.
        timeline:          Lista de dicts con keys:
                           Fecha, Tipo, Concepto, Presupuesto, Cobrado, Certificado.
    Returns:
        Bytes del PDF.
    """
    buffer = BytesIO()
    available_width = A4[0] - 50 * mm

    subtitle_parts = [obra_nombre]
    if cliente:
        subtitle_parts.append(f"Cliente: {cliente}")
    subtitle = "  |  ".join(subtitle_parts)

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30 * mm,
        rightMargin=20 * mm,
        topMargin=30 * mm,
        bottomMargin=20 * mm,
    )

    def _frame(d):
        return Frame(d.leftMargin, d.bottomMargin, d.width, d.height, id="normal")

    def _on_page(c, d):
        _obra_page_template(c, d, "RESUMEN FINANCIERO DE OBRA", subtitle, fecha_generacion)

    doc.addPageTemplates([PageTemplate(id="resumen", frames=[_frame(doc)], onPage=_on_page)])

    _metric_label = ParagraphStyle(
        "ResMetricLabel", parent=_styles["Normal"],
        fontSize=6.5, leading=9, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#9CA3AF"), spaceAfter=1 * mm,
    )
    _metric_value = ParagraphStyle(
        "ResMetricValue", parent=_styles["Normal"],
        fontSize=12, leading=15, fontName="Helvetica-Bold",
        textColor=_C_RESUMEN_HDR,
    )
    _metric_sub = ParagraphStyle(
        "ResMetricSub", parent=_styles["Normal"],
        fontSize=7, leading=9, textColor=colors.HexColor("#6B7280"),
        spaceBefore=1 * mm,
    )
    _balance_pos = ParagraphStyle(
        "ResBalPos", parent=_styles["Normal"],
        fontSize=7.5, leading=10, textColor=colors.HexColor("#D97706"),
        spaceBefore=1 * mm,
    )
    _balance_neg = ParagraphStyle(
        "ResBalNeg", parent=_styles["Normal"],
        fontSize=7.5, leading=10, textColor=colors.HexColor("#DC2626"),
        spaceBefore=1 * mm,
    )
    _section_hdr = ParagraphStyle(
        "ResSectionHdr", parent=_styles["Normal"],
        fontSize=8, leading=10, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#9CA3AF"),
        spaceBefore=8 * mm, spaceAfter=2 * mm,
        borderPadding=(0, 0, 2, 0),
    )
    _tl_cell = ParagraphStyle(
        "ResTlCell", parent=_styles["Normal"], fontSize=7.5, leading=10,
    )
    _tl_cell_r = ParagraphStyle(
        "ResTlCellR", parent=_styles["Normal"], fontSize=7.5, leading=10, alignment=2,
    )
    _tl_hdr = ParagraphStyle(
        "ResTlHdr", parent=_styles["Normal"], fontSize=7.5, leading=10,
        fontName="Helvetica-Bold", textColor=colors.white,
    )
    _tl_hdr_r = ParagraphStyle(
        "ResTlHdrR", parent=_styles["Normal"], fontSize=7.5, leading=10,
        fontName="Helvetica-Bold", textColor=colors.white, alignment=2,
    )

    from reportlab.platypus import HRFlowable
    story: list = [Spacer(1, 2 * mm)]

    # ── Métricas en tabla 3 columnas ───────────────────────────────────────
    pct_cert = (total_certificado / total_presupuesto * 100) if total_presupuesto else 0
    pct_cob  = (total_cobrado / total_presupuesto * 100) if total_presupuesto else 0

    def _metric_cell(label: str, value: float, pct: float | None = None) -> list:
        cell = [
            Paragraph(label, _metric_label),
            Paragraph(f"Gs. {_fmt_guaranies(value)}", _metric_value),
        ]
        if pct is not None:
            cell.append(Paragraph(f"{pct:.1f}% del contrato".replace(".", ","), _metric_sub))
        return cell

    col_w = available_width / 3
    metrics_data = [[
        _metric_cell("PRESUPUESTO CONTRATADO", total_presupuesto),
        _metric_cell("TOTAL CERTIFICADO", total_certificado, pct_cert),
        _metric_cell("TOTAL COBRADO", total_cobrado, pct_cob),
    ]]
    metrics_table = Table(metrics_data, colWidths=[col_w, col_w, col_w])
    metrics_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#E5E7EB")),
        ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.HexColor("#E5E7EB")),
        ("LINEBEFORE", (2, 0), (2, 0), 0.5, colors.HexColor("#E5E7EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB"), spaceAfter=0))

    # ── Balances ───────────────────────────────────────────────────────────
    def _balance_cell(label: str, monto: float, label_pos: str, label_neg: str) -> list:
        style = _balance_neg if monto < 0 else _balance_pos
        nota = label_neg if monto < 0 else label_pos
        return [
            Paragraph(label, _metric_label),
            Paragraph(f"Gs. {_fmt_guaranies(abs(monto))}", _metric_value),
            Paragraph(nota, style),
        ]

    bal_data = [[
        _balance_cell(
            "SALDO PENDIENTE (Ppto − Cobrado)", saldo_pendiente,
            "Por cobrar del cliente", "Cobrado en exceso del contrato",
        ),
        _balance_cell(
            "BALANCE (Cobrado − Certificado)", balance,
            "Cobrado por delante de lo certificado", "Certificado por delante de los cobros",
        ),
    ]]
    bal_table = Table(bal_data, colWidths=[available_width / 2, available_width / 2])
    bal_table.setStyle(TableStyle([
        ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.HexColor("#E5E7EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(bal_table)

    # ── Timeline ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB"), spaceAfter=0))
    story.append(Paragraph("MOVIMIENTOS", _section_hdr))

    # Fecha | Tipo | Concepto | Presupuesto | Cobrado | Certificado
    # Columnas de montos reducidas ~7mm respecto al diseño original
    _money_w = 23 * mm
    _fixed = 18 * mm + 26 * mm + _money_w * 3  # 113mm
    concepto_w = max(available_width - _fixed, 50 * mm)
    col_widths_tl = [18 * mm, 26 * mm, concepto_w, _money_w, _money_w, _money_w]

    tl_data = [[
        Paragraph("Fecha", _tl_hdr),
        Paragraph("Tipo", _tl_hdr),
        Paragraph("Concepto", _tl_hdr),
        Paragraph("Presupuesto", _tl_hdr_r),
        Paragraph("Cobrado", _tl_hdr_r),
        Paragraph("Certificado", _tl_hdr_r),
    ]]
    style_cmds_tl = [
        ("BACKGROUND", (0, 0), (-1, 0), _C_RESUMEN_HDR),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    total_pres_tl = total_cert_tl = total_cob_tl = 0.0

    for i, r in enumerate(timeline, start=1):
        tipo       = r.get("Tipo", "")
        pres_val   = r.get("Presupuesto")
        cob_val    = r.get("Cobrado")
        cert_val   = r.get("Certificado")

        pres_str = _fmt_guaranies(pres_val) if pres_val is not None else ""
        cob_str  = _fmt_guaranies(cob_val)  if cob_val  is not None else ""
        cert_str = _fmt_guaranies(cert_val) if cert_val is not None else ""

        if pres_val:  total_pres_tl += float(pres_val)
        if cob_val:   total_cob_tl  += float(cob_val)
        if cert_val:  total_cert_tl += float(cert_val)

        if i % 2 == 0:
            style_cmds_tl.append(("BACKGROUND", (0, i), (-1, i), _C_RESUMEN_ALT))

        tl_data.append([
            Paragraph(_safe(r.get("Fecha", "")), _tl_cell),
            Paragraph(_safe(tipo), _tl_cell),
            Paragraph(_safe(r.get("Concepto", "")), _tl_cell),
            Paragraph(pres_str, _tl_cell_r),
            Paragraph(cob_str,  _tl_cell_r),
            Paragraph(cert_str, _tl_cell_r),
        ])

    # Totals row
    totals_idx = len(tl_data)
    tl_data.append([
        Paragraph("", _tl_cell),
        Paragraph("", _tl_cell),
        Paragraph("<b>TOTAL</b>", _tl_cell),
        Paragraph(f"<b>{_fmt_guaranies(total_pres_tl)}</b>", _tl_cell_r),
        Paragraph(f"<b>{_fmt_guaranies(total_cob_tl)}</b>",  _tl_cell_r),
        Paragraph(f"<b>{_fmt_guaranies(total_cert_tl)}</b>", _tl_cell_r),
    ])
    style_cmds_tl.append(("BACKGROUND", (0, totals_idx), (-1, totals_idx), _C_RESUMEN_TOTAL))
    style_cmds_tl.append(("LINEABOVE", (0, totals_idx), (-1, totals_idx), 1.2, _C_RESUMEN_HDR))

    tl_table = Table(tl_data, colWidths=col_widths_tl, repeatRows=1, splitByRow=True)
    tl_table.setStyle(TableStyle(style_cmds_tl))
    story.append(tl_table)

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Planilla de Pagos — Tool 7
# ---------------------------------------------------------------------------

def _build_planilla_table(
    lineas: list[dict],
    obra_names: dict[str, str],
    trab_names: dict[str, str],
    available_width: float,
) -> list:
    """Construye la tabla de la planilla de pagos: una tabla por obra + Spacer entre ellas."""
    from collections import defaultdict

    W = available_width
    col_widths = [W * 0.4375, W * 0.3125, W * 0.15625, W * 0.09375]

    _base_style = [
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7b8")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]

    story_elements: list = []
    grand_total = 0.0

    by_obra: dict = defaultdict(list)
    for line in lineas:
        by_obra[line["obra_id"]].append(line)

    for obra_id, obra_lines in by_obra.items():
        obra_name = obra_names.get(obra_id, obra_id)
        rows: list = []
        style_cmds = list(_base_style)
        row_idx = 0

        # Obra header row — spans all columns
        rows.append([
            _p(obra_name, _OR_OBRA),
            _p("", _OR_OBRA),
            _p("", _OR_OBRA),
            _p("", _OR_OBRA),
        ])
        style_cmds.append(("BACKGROUND",    (0, row_idx), (-1, row_idx), _C_OBRA))
        style_cmds.append(("SPAN",          (0, row_idx), (-1, row_idx)))
        style_cmds.append(("TOPPADDING",    (0, row_idx), (-1, row_idx), 3))
        style_cmds.append(("BOTTOMPADDING", (0, row_idx), (-1, row_idx), 3))
        row_idx += 1

        # Column headers
        rows.append([
            _p("Trabajador",  _OR_HDR),
            _p("Concepto",    _OR_HDR),
            _p("Monto (Gs.)", _OR_HDR),
            _p("Método",      _OR_HDR),
        ])
        style_cmds.append(("BACKGROUND",    (0, row_idx), (-1, row_idx), _C_RUBRO))
        style_cmds.append(("ALIGN",         (2, row_idx), (2, row_idx),  "RIGHT"))
        style_cmds.append(("TOPPADDING",    (0, row_idx), (-1, row_idx), 2))
        style_cmds.append(("BOTTOMPADDING", (0, row_idx), (-1, row_idx), 2))
        row_idx += 1

        # Data rows
        obra_total = 0.0
        alt = False
        for line in obra_lines:
            trab_name = trab_names.get(line["trab_id"], line["trab_id"])
            monto = float(line.get("monto", 0))
            metodo = line.get("metodo", "")
            if metodo == "Transferencia":
                metodo_p = Paragraph('<font color="#E8622A"><b>TRANSF.</b></font>', _OR_ITEM)
            else:
                metodo_p = Paragraph('<font color="#6B7280">EFECTIVO</font>', _OR_ITEM)

            rows.append([
                _p(trab_name,                  _OR_ITEM),
                _p(line.get("concepto", ""),   _OR_ITEM),
                _p(_fmt_gs(monto),             _OR_ITEM),
                metodo_p,
            ])
            style_cmds.append(("ALIGN", (2, row_idx), (2, row_idx), "RIGHT"))
            if alt:
                style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _C_ALT))
            alt = not alt
            obra_total += monto
            row_idx += 1

        # Subtotal row
        rows.append([
            _p(f"Subtotal {obra_name}", _OR_SUB),
            _p("",                      _OR_SUB),
            _p(_fmt_gs(obra_total),     _OR_SUB),
            _p("",                      _OR_SUB),
        ])
        style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _C_SUB))
        style_cmds.append(("ALIGN",      (2, row_idx), (2, row_idx),  "RIGHT"))
        style_cmds.append(("LINEABOVE",  (0, row_idx), (-1, row_idx), 0.8, _C_RUBRO))
        grand_total += obra_total

        table = Table(rows, colWidths=col_widths, splitByRow=True)
        table.setStyle(TableStyle(style_cmds))
        story_elements.append(table)
        story_elements.append(Spacer(1, 4 * mm))  # espacio entre obras

    # Grand total + desglose (tabla aparte)
    efectivo_total = sum(float(l.get("monto", 0)) for l in lineas if l.get("metodo") == "Efectivo")
    transfer_total = sum(float(l.get("monto", 0)) for l in lineas if l.get("metodo") == "Transferencia")

    tot_rows = [
        [
            _p("TOTAL GENERAL", _OR_SUB),
            _p("",              _OR_SUB),
            _p(_fmt_gs(grand_total), _OR_SUB),
            _p("",              _OR_SUB),
        ],
        [
            _p(f"Efectivo: {_fmt_gs(efectivo_total)}", _OR_ITEM),
            _p(f"Transferencia: {_fmt_gs(transfer_total)}", _OR_ITEM),
            _p("", _OR_ITEM),
            _p("", _OR_ITEM),
        ],
    ]
    tot_style = list(_base_style) + [
        ("BACKGROUND", (0, 0), (-1, 0), _C_TOTAL),
        ("ALIGN",      (2, 0), (2, 0),  "RIGHT"),
        ("LINEABOVE",  (0, 0), (-1, 0), 1.5, _DK),
        ("BACKGROUND", (0, 1), (-1, 1), _C_TOTAL),
    ]
    tot_table = Table(tot_rows, colWidths=col_widths)
    tot_table.setStyle(TableStyle(tot_style))
    story_elements.append(tot_table)

    _letras_style = ParagraphStyle(
        "PlanillaLetrasStyle",
        parent=_styles["Normal"],
        fontSize=7.5, leading=10,
        fontName="Helvetica-Oblique",
        textColor=_DK,
    )
    letras = _guaranies_en_letras(int(grand_total))
    letras_p = Paragraph(f"Son Guaraníes: {_safe(letras)}", _letras_style)

    story_elements.append(Spacer(1, 3 * mm))
    story_elements.append(letras_p)

    return story_elements


def generate_planilla_pagos_pdf(
    lineas: list[dict],
    fecha,
    obra_names: dict[str, str],
    trab_names: dict[str, str],
) -> bytes:
    """Genera la planilla semanal de pagos en PDF.

    Args:
        lineas:     Lista de dicts con obra_id, trab_id, concepto, monto, metodo.
        fecha:      Objeto date con la fecha de la planilla.
        obra_names: {obra_id: obra_name}
        trab_names: {trab_id: trab_name}

    Returns:
        Bytes del PDF generado.
    """
    buffer = BytesIO()
    available_width = A4[0] - 50 * mm

    _MESES = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    fecha_larga = f"{fecha.day} de {_MESES[fecha.month - 1]} de {fecha.year}"
    fecha_corta = f"{fecha.day}/{fecha.month:02d}/{fecha.year}"

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30 * mm,
        rightMargin=20 * mm,
        topMargin=30 * mm,
        bottomMargin=20 * mm,
    )

    def _frame(d):
        return Frame(d.leftMargin, d.bottomMargin, d.width, d.height, id="normal")

    def _on_page(c, d):
        _obra_page_template(c, d, "PLANILLA DE PAGOS", fecha_larga, fecha_corta)

    doc.addPageTemplates([
        PageTemplate(id="planilla", frames=[_frame(doc)], onPage=_on_page),
    ])

    story: list = [Spacer(1, 2 * mm)]

    if not lineas:
        _no_data_style = ParagraphStyle(
            "PlanillaNoData", parent=_styles["Normal"],
            fontSize=9, textColor=colors.HexColor("#6B7280"),
        )
        story.append(Paragraph("Sin pagos registrados.", _no_data_style))
    else:
        story.extend(_build_planilla_table(lineas, obra_names, trab_names, available_width))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
