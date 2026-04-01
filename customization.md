# JS Tools — Customization Guide

## Adding a New Tool
1. Create `pages/NN_nombre_herramienta.py`.
2. Add at the top:
   ```python
   TOOL = ToolMetadata(
       name="Nombre",
       description="Descripción breve.",
       icon="🔧",
       page_file="NN_nombre_herramienta.py",
   )
   ```
3. Done — registry auto-discovers it. No changes to `app.py` or `registry.py`.

---

## Adding Airtable Fields
1. Find the field ID in Airtable (API docs or field settings URL — starts with `fld...`). Can also be retrieved via the Airtable API using the token in `.env`:
   ```bash
   curl https://api.airtable.com/v0/meta/bases/app2cOTrbiNx10o2d/tables \
     -H "Authorization: Bearer <token>"
   ```
2. Add to the relevant table in `config.py`:
   ```python
   "NombreCampo": "fldXXXXXXXXXXXXXX",
   ```
3. Click **🔄 Actualizar datos** in the sidebar to invalidate the cache.

---

## Adjusting Column Widths (Tool 2)
`_DETAIL_COLUMNS` in `02_resumen_pagos.py` controls both the PDF and web table widths:

```python
_DETAIL_COLUMNS = [
    {"key": "fecha",      "label": "Fecha",             "width_mm": 20, ...},
    {"key": "concepto",   "label": "Concepto",          "width_mm": 60, ...},
    {"key": "tipo",       "label": "Tipo / Estado",     "width_mm": 22, ...},
    {"key": "monto_pres", "label": "Presupuesto (Gs.)", "width_mm": 28, ...},
    {"key": "monto_pago", "label": "Pago (Gs.)",        "width_mm": 28, ...},
    {"key": "metodo",     "label": "Método",            "width_mm": 22, ...},
]
```
- Change `width_mm` → PDF column width changes, web table pixel width changes (`mm × 3.78`).
- PDF total available width: 160mm (A4 210mm − 30mm left − 20mm right). Columns auto-scale if total exceeds it.

---

## PDF Margins

**Tools 1–3** (`SimpleDocTemplate`):
- `leftMargin=30mm`, `rightMargin=20mm`, `topMargin=25mm`, `bottomMargin=25mm`

**Tool 4 — Obra reports** (`BaseDocTemplate` + `PageTemplate`):
- `leftMargin=30mm`, `rightMargin=20mm`, `topMargin=30mm`, `bottomMargin=20mm`
- Extra top margin to accommodate the logo + title + subtitle header drawn via `_obra_page_template()`.

`available_width = A4[0] - 50 * mm` in both cases (leftMargin + rightMargin = 50mm).

---

## PDF Color Palette — Hierarchical Reports (Tool 4)

These constants are defined in `generators/pdf_generator.py` and **must be reused** for any future obra-style report. Do not introduce new colors.

| Constant | Hex | Usage |
|----------|-----|-------|
| `_C_OBRA` | `#1a252f` | Obra-level row background (darkest) |
| `_C_SECTOR` | `#2e4053` | Sector-level row background |
| `_C_RUBRO` | `#5d6d7e` | Rubro-level row background + column headers |
| `_C_SUB` | `#d5d8dc` | Subtotal rows (per rubro) |
| `_C_TOTAL` | `#aab7b8` | Grand total row |
| `_C_ALT` | `#f2f3f4` | Alternating data row background |
| `colors.white` | `#ffffff` | Default data row background |
| `#E8622A` | (accent) | Header separator line, brand orange |

All text on dark backgrounds (`_C_OBRA`, `_C_SECTOR`, `_C_RUBRO`) uses `textColor=colors.white`.
Text on light backgrounds uses `textColor=colors.HexColor("#1a252f")` (dark).

## PDF Typography — Hierarchical Reports (Tool 4)

Paragraph styles defined in `generators/pdf_generator.py`. **Reuse these, do not redefine.**

| Style | Font | Size | Weight | Color | Use |
|-------|------|------|--------|-------|-----|
| `_OR_HDR` | Helvetica | 7.5pt | Bold | White | Column headers |
| `_OR_OBRA` | Helvetica | 8pt | Bold | White | Obra-level rows |
| `_OR_SECTOR` | Helvetica | 7.5pt | Bold | White | Sector-level rows |
| `_OR_RUBRO` | Helvetica | 7pt | Bold | White | Rubro rows (detail tables) |
| `_OR_RUBRO_RESUMEN` | Helvetica | 7pt | Bold | Dark | Rubro rows (summary table only) |
| `_OR_ITEM` | Helvetica | 7pt | Normal | Dark | Data rows |
| `_OR_SUB` | Helvetica | 7pt | Bold | Dark | Subtotal rows |

## PDF Page Header — Obra Reports

Every page is drawn by `_obra_page_template(canvas, doc, title, subtitle, fecha)` in `pdf_generator.py`:
- **Top-left:** `assets/logo.png` at `(30mm, A4[1]−18mm)`, 28×11mm
- **Top-center:** section title in Helvetica-Bold 12pt (e.g. "RESUMEN GENERAL")
- **Top-right:** `Generado: DD/M/YYYY` in Helvetica-Bold 8pt
- **Below title:** subtitle `Cliente: X | Obra: Y` in Helvetica 8.5pt, muted color `#5d6d7e`
- **Separator:** 1.2pt line in `#E8622A` (brand orange), spanning full text width
- **Bottom-center:** "Página X de Y" in Helvetica 7pt, color `#6B7280` (drawn by `_NumberedCanvas`)

---

## Design Principles

**Every tool must be: minimalist · intuitive · professional.**

- Remove before you add — if an element doesn't earn its place, cut it
- One clear action per context — don't stack buttons without hierarchy
- Labels concise, captions muted, data prominent
- Dark-mode compatible — no hardcoded light colors, always use `--js-*` variables
- Consistent spacing: `st.divider()` between sections, `st.container(border=True)` for cards

---

## CSS Design System

All tools share the same CSS custom properties. **These values are canonical** — copy them exactly when adding a new tool (injected per page via `st.markdown`):

```css
:root {
    --js-accent:  #E8622A;  /* brand orange — buttons, headers, PDF accent */
    --js-success: #27AE60;  /* green — found, original, confirmed */
    --js-danger:  #E74C3C;  /* red — missing, duplicate, errors */
    --js-warn:    #E67E22;  /* amber — line duplicates, warnings */
    --js-muted:   #6B7280;  /* gray — subtitles, captions, metadata */
    --js-border:  rgba(255,255,255,0.09);  /* subtle dividers, card borders */
    --js-surface: rgba(255,255,255,0.03);  /* card/surface backgrounds */
}
/* Shared base — every tool defines these */
.js-sub  { color: var(--js-muted); font-size: .875rem; margin-top: -10px; margin-bottom: 24px; }
.js-pill { display: inline-block; border-radius: 3px; padding: 2px 8px; font-size: .68rem;
           font-weight: 700; letter-spacing: .8px; text-transform: uppercase; }
```

**Status pills** (used in Tool 3):
```html
<span class="js-pill js-orig">Original</span>   <!-- green -->
<span class="js-pill js-dup">Duplicado</span>    <!-- red -->
<span class="js-pill js-line">Línea dup.</span>  <!-- amber -->
```

**Group header** (Tool 3 document cards):
```html
<div class="js-grp-hdr">
  <div>
    <div class="js-grp-nro">001-001-0000001</div>
    <div class="js-grp-prov">Proveedor S.A.</div>
  </div>
  <span class="js-grp-tag">2 problemas · 3 en riesgo</span>
</div>
```

---

## UI Conventions
- **Load buttons:** "📥 Cargar" (not "Buscar" or other labels).
- **Date filter expander:** always `expanded=True`.
- **Extracted values:** show via `st.expander("Ver valores cargados")` after loading.
- **Results:** render INSIDE the active tab — never globally below tabs.
- **Limpiar button:** one per tab, independent of other tabs.
- **No trailing summaries** in Claude responses — user can read the diff.
- **Only change what was asked.** If scope is unclear, ask before acting.




## Streamlit UI Standards

### Layout
- Always use `st.set_page_config(layout="wide")`
- Use columns to organize content, never stack everything vertically
- Group related elements inside `st.container()` or `with st.expander()`
- Add consistent spacing with `st.divider()` between sections

### Styling
- Always inject custom CSS via `st.markdown("<style>...</style>", unsafe_allow_html=True)`
- Use a consistent color palette — define it once and reuse
- Cards: simulate with bordered containers using custom CSS
- Never use default Streamlit colors alone — always customize

### Components
- Metrics: always use `st.metric()` with delta where relevant
- Tables: prefer `st.dataframe()` with `use_container_width=True`
- Sidebars: use for filters and navigation, never for main content
- Avoid walls of text — break with columns, expanders, tabs

### General
- Every page needs a clear visual hierarchy: title → subtitle → content
- Mobile is not a priority, but desktop should look professional