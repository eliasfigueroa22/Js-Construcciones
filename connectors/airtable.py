"""Conector de Airtable con traducción de field IDs.

Usa pyairtable con use_field_ids=True para desacoplar el código
de los nombres de campo visibles en Airtable.
"""

import streamlit as st
from pyairtable import Api

from config import AIRTABLE_BASE_ID, TABLES, get_secret


def _normalize_value(val):
    """Normaliza valores de Airtable.

    - Listas de un solo elemento → elemento suelto
    - None → cadena vacía
    """
    if isinstance(val, list):
        return val[0] if len(val) == 1 else val
    return val if val is not None else ""


@st.cache_data(ttl=None, show_spinner="Consultando Airtable...")
def get_all_records(
    table_key: str, field_keys: list[str] | None = None
) -> list[dict]:
    """Obtiene todos los registros de una tabla, traduciendo field IDs a claves legibles.

    Args:
        table_key: Clave en config.TABLES (ej. "facturas").
        field_keys: Lista de claves a solicitar. None = todas.

    Returns:
        Lista de dicts con claves legibles (no field IDs).

    Raises:
        ConnectionError: Si la conexión a Airtable falla.
    """
    table_cfg = TABLES[table_key]
    fields_map = table_cfg["fields"]

    if field_keys:
        field_ids = [fields_map[k] for k in field_keys]
    else:
        field_keys = list(fields_map.keys())
        field_ids = list(fields_map.values())

    id_to_key = {fields_map[k]: k for k in field_keys}

    try:
        api = Api(get_secret("AIRTABLE_API_KEY"))
        table = api.table(AIRTABLE_BASE_ID, table_cfg["id"])
        records = table.all(fields=field_ids, use_field_ids=True)
    except Exception as exc:
        raise ConnectionError(
            f"Error al conectar con Airtable (tabla '{table_key}'): {exc}"
        ) from exc

    return [
        {
            "_id": rec["id"],
            **{
                id_to_key.get(fid, fid): _normalize_value(val)
                for fid, val in rec["fields"].items()
            },
        }
        for rec in records
    ]


@st.cache_data(ttl=None, show_spinner="Cargando nombres...")
def get_record_names(table_id: str, primary_field_id: str) -> dict[str, str]:
    """Devuelve un dict {record_id: primary_field_value} para una tabla.

    Útil para resolver linked record IDs a nombres legibles.
    """
    try:
        api = Api(get_secret("AIRTABLE_API_KEY"))
        table = api.table(AIRTABLE_BASE_ID, table_id)
        records = table.all(fields=[primary_field_id], use_field_ids=True)
    except Exception as exc:
        raise ConnectionError(
            f"Error al obtener nombres de tabla '{table_id}': {exc}"
        ) from exc

    return {
        rec["id"]: rec["fields"].get(primary_field_id, rec["id"])
        for rec in records
    }


def create_record(table_key: str, fields: dict) -> str:
    """Crea un registro en Airtable usando claves legibles del config.

    Returns:
        El ID del registro creado (ej. "recXXXXXXXXXXXXXX").

    Raises:
        ConnectionError: Si falla la conexión.
    """
    table_cfg = TABLES[table_key]
    fields_map = table_cfg["fields"]
    field_data = {fields_map[k]: v for k, v in fields.items() if k in fields_map}
    try:
        api = Api(get_secret("AIRTABLE_API_KEY"))
        table = api.table(AIRTABLE_BASE_ID, table_cfg["id"])
        created = table.create(field_data)
        return created["id"]
    except Exception as exc:
        raise ConnectionError(
            f"Error al crear registro en '{table_key}': {exc}"
        ) from exc


def update_record(table_key: str, record_id: str, fields: dict) -> None:
    """Actualiza un registro existente en Airtable usando claves legibles del config.

    Llamar get_all_records.clear() después para invalidar el cache.

    Args:
        table_key: Clave en config.TABLES (ej. "MedicionCabecera").
        record_id: El ID del registro a actualizar (obtenido como "_id").
        fields: Dict con pares {clave_legible: valor}.

    Raises:
        ConnectionError: Si falla la conexión o la actualización.
    """
    table_cfg = TABLES[table_key]
    fields_map = table_cfg["fields"]
    field_data = {fields_map[k]: v for k, v in fields.items() if k in fields_map}
    try:
        api = Api(get_secret("AIRTABLE_API_KEY"))
        table = api.table(AIRTABLE_BASE_ID, table_cfg["id"])
        table.update(record_id, field_data, use_field_ids=True)
    except Exception as exc:
        raise ConnectionError(
            f"Error al actualizar registro '{record_id}' en '{table_key}': {exc}"
        ) from exc


def delete_record(table_key: str, record_id: str) -> None:
    """Elimina un registro de Airtable por su ID.

    Llamar get_all_records.clear() después para invalidar el cache.

    Raises:
        ConnectionError: Si falla la conexión o la eliminación.
    """
    table_cfg = TABLES[table_key]
    try:
        api = Api(get_secret("AIRTABLE_API_KEY"))
        table = api.table(AIRTABLE_BASE_ID, table_cfg["id"])
        table.delete(record_id)
    except Exception as exc:
        raise ConnectionError(
            f"Error al eliminar registro '{record_id}' en '{table_key}': {exc}"
        ) from exc
