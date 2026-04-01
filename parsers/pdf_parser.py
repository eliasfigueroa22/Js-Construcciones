"""Extracción de datos tabulares desde PDFs con pdfplumber."""

import logging
import re
from datetime import date, datetime
from io import BytesIO

import pdfplumber

logger = logging.getLogger(__name__)


def extract_pdf_columns(uploaded_file) -> list[str]:
    """Detecta todos los nombres de columna únicos en las tablas del PDF.

    Devuelve los encabezados normalizados (stripped, sin saltos de línea)
    en orden de aparición, sin duplicados.
    """
    uploaded_file.seek(0)
    seen: set[str] = set()
    columns: list[str] = []

    with pdfplumber.open(BytesIO(uploaded_file.read())) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                if not table or not table[0]:
                    continue
                for h in table[0]:
                    name = (h or "").strip().replace("\n", " ")
                    if name and name not in seen:
                        seen.add(name)
                        columns.append(name)
    return columns


def extract_column_from_pdf(
    uploaded_file, column_name: str, *, strip: bool = True
) -> list[str]:
    """Extrae una columna por nombre de las tablas de un PDF.

    Busca el encabezado en todas las tablas de todas las páginas.
    El match de encabezado es case-insensitive, stripped, y reemplaza
    saltos de línea internos por espacios.

    Args:
        uploaded_file: Archivo subido vía st.file_uploader (BytesIO-like).
        column_name: Nombre de la columna a extraer.
        strip: Si True, elimina espacios en los valores extraídos.

    Returns:
        Lista de valores (strings) de la columna encontrada.

    Raises:
        ValueError: Si la columna no se encuentra en ninguna tabla.
    """
    uploaded_file.seek(0)
    values: list[str] = []
    target = column_name.strip().lower().replace("\n", " ")

    with pdfplumber.open(BytesIO(uploaded_file.read())) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                if not table or not table[0]:
                    continue
                # Normalizar encabezados
                headers = [
                    (h or "").strip().lower().replace("\n", " ")
                    for h in table[0]
                ]
                if target not in headers:
                    continue
                col_idx = headers.index(target)
                for row in table[1:]:
                    if row and col_idx < len(row):
                        cell = row[col_idx]
                        if cell is not None:
                            val = cell.strip() if strip else cell
                            if val:
                                values.append(val)

    if not values:
        raise ValueError(
            f'No se encontró la columna "{column_name}" en el PDF. '
            f"Verificá que el PDF tenga tablas con esa columna."
        )
    return values


# -- KuDE (Factura Electrónica Paraguay / SIFEN) ------------------------------

def _search_kude_field(text: str, label: str) -> str | None:
    """Busca un campo por etiqueta en el texto del KuDE.

    Intenta varias estrategias: misma línea después de ':', línea siguiente,
    y match con regex flexible para variantes de formato.
    """
    for line_idx, line in enumerate(text.splitlines()):
        if label.lower() in line.lower():
            # Valor después de ':' en la misma línea
            if ":" in line:
                after = line.split(":", 1)[1].strip()
                if after:
                    return after
            # Valor en la línea siguiente
            lines = text.splitlines()
            if line_idx + 1 < len(lines):
                next_line = lines[line_idx + 1].strip()
                if next_line:
                    return next_line
    return None


def _extract_emisor_name(page_text: str) -> str | None:
    """Extrae el nombre del emisor (proveedor real) del encabezado del KuDE.

    En el KuDE de SIFEN, el nombre del emisor aparece en el encabezado ANTES
    de su 'Dirección:'. El campo 'Razón Social' que aparece más abajo es el
    del receptor (comprador), no el del emisor.
    """
    lines = [l.strip() for l in page_text.splitlines()]
    skip_patterns = [
        r"^kude",
        r"factura electr",
        r"^\d{3}-\d{3}-\d+",
        r"^ruc",
        r"^timbrado",
        r"^fecha",
        r"^\d+[-\u2013]\d+$",
    ]

    for i, line in enumerate(lines):
        if re.search(r"direcci[oó]n\s*:", line, re.IGNORECASE):
            for j in range(i - 1, max(i - 6, -1), -1):
                candidate = lines[j]
                if not candidate:
                    continue
                if any(re.search(p, candidate, re.IGNORECASE) for p in skip_patterns):
                    continue
                return candidate
            break  # solo buscar en el primer "Dirección:" (bloque del emisor)
    return None


def _parse_kude_page(page_text: str) -> dict | None:
    """Parsea el texto de una página individual como KuDE.

    Cada página de un KuDE PDF (o de un PDF consolidado con múltiples KuDEs)
    puede contener una factura electrónica independiente.

    Returns:
        Dict con datos extraídos, o None si la página no contiene un KuDE válido
        (no tiene número de factura con patrón NNN-NNN-NNNNNNN).
    """
    if not page_text or not page_text.strip():
        return None

    result: dict = {
        "numero_factura": None,
        "numero_simple": None,
        "proveedor": None,
        "ruc_emisor": None,
        "fecha": None,
        "monto_total": None,
        "cdc": None,
    }

    # -- Número de factura: buscar patrón NNN-NNN-NNNNNNN
    factura_match = re.search(r"\d{3}-\d{3}-\d{5,10}", page_text)
    if not factura_match:
        return None
    result["numero_factura"] = factura_match.group()
    last_segment = result["numero_factura"].rsplit("-", 1)[-1]
    result["numero_simple"] = str(int(last_segment))

    # -- Proveedor: nombre del emisor del encabezado (antes de "Dirección:")
    # NO usar "Razón Social" porque ese campo pertenece al receptor (comprador)
    proveedor = _extract_emisor_name(page_text)
    if not proveedor:
        # Fallback: Razón Social (puede ser el receptor, pero mejor que nada)
        proveedor = _search_kude_field(page_text, "Razón Social")
        if not proveedor:
            proveedor = _search_kude_field(page_text, "Nombre / Razón Social")
    if proveedor:
        result["proveedor"] = proveedor

    # -- RUC emisor
    ruc_raw = _search_kude_field(page_text, "RUC")
    if ruc_raw:
        result["ruc_emisor"] = re.sub(r"\s*-\s*", "-", ruc_raw.split("\n")[0].strip())

    # -- Fecha de emisión
    fecha_raw = _search_kude_field(page_text, "Fecha de Emisión")
    if not fecha_raw:
        fecha_raw = _search_kude_field(page_text, "Fecha Emisión")
    if fecha_raw:
        fecha_match = re.search(r"(\d{2}/\d{2}/\d{4})", fecha_raw)
        if fecha_match:
            try:
                result["fecha"] = datetime.strptime(
                    fecha_match.group(1), "%d/%m/%Y"
                ).date()
            except ValueError:
                pass

    # -- Monto total: formato paraguayo (punto = separador de miles)
    for label in ["TOTAL DE LA OPERACIÓN", "Total de la Operación", "TOTAL"]:
        monto_raw = _search_kude_field(page_text, label)
        if monto_raw:
            cleaned = re.sub(r"[^\d.,]", "", monto_raw)
            if "," not in cleaned:
                cleaned = cleaned.replace(".", "")
            else:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            try:
                result["monto_total"] = float(cleaned)
                break
            except ValueError:
                continue

    # -- CDC: código de 44 dígitos, puede tener espacios
    cdc_raw = _search_kude_field(page_text, "CDC")
    if cdc_raw:
        digits = re.sub(r"\D", "", cdc_raw)
        if len(digits) >= 44:
            result["cdc"] = digits[:44]
    if not result["cdc"]:
        cdc_pattern = re.search(r"(?:\d[\s]*){44}", page_text)
        if cdc_pattern:
            result["cdc"] = re.sub(r"\D", "", cdc_pattern.group())[:44]

    return result


def extract_from_kude(uploaded_file) -> list[dict]:
    """Extrae datos de un KuDE PDF, tratando cada página como posible factura.

    Soporta tanto KuDEs de una sola página como PDFs consolidados
    con múltiples facturas electrónicas (una por página).
    Las páginas que no contengan un KuDE válido se omiten silenciosamente.

    Args:
        uploaded_file: Archivo subido vía st.file_uploader (BytesIO-like).

    Returns:
        Lista de dicts, cada uno con claves: numero_factura, numero_simple,
        proveedor, ruc_emisor, fecha, monto_total, cdc.

    Raises:
        RuntimeError: Si el PDF no se puede abrir o no contiene ningún KuDE.
    """
    uploaded_file.seek(0)
    try:
        pdf_bytes = uploaded_file.read()
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page_texts = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo leer el PDF como KuDE: {exc}"
        ) from exc

    # Parsear cada página como posible KuDE independiente
    invoices: list[dict] = []
    seen_numbers: set[str] = set()

    for page_text in page_texts:
        parsed = _parse_kude_page(page_text)
        if parsed is None:
            continue
        # Evitar duplicados (páginas de continuación del mismo KuDE)
        nf = parsed["numero_factura"]
        if nf in seen_numbers:
            continue
        seen_numbers.add(nf)
        invoices.append(parsed)

    if not invoices:
        raise RuntimeError(
            "No se encontró ninguna factura electrónica en el PDF. "
            "Verificá que sea un KuDE válido."
        )

    return invoices


def extract_multiple_kudes(uploaded_files: list) -> tuple[list[dict], list[str]]:
    """Extrae datos de múltiples KuDE PDFs.

    Cada archivo puede contener una o varias facturas (una por página).
    Los archivos que fallan se omiten con un warning.

    Returns:
        Tupla (resultados, errores):
        - resultados: lista de dicts (estructura de _parse_kude_page + "archivo")
        - errores: lista de nombres de archivos que fallaron
    """
    results: list[dict] = []
    errors: list[str] = []

    for f in uploaded_files:
        try:
            invoices = extract_from_kude(f)
            for inv in invoices:
                inv["archivo"] = f.name
                results.append(inv)
        except (RuntimeError, Exception) as exc:
            errors.append(f.name)
            logger.warning("No se pudo procesar KuDE '%s': %s", f.name, exc)

    return results, errors
