"""Conector Supabase para JS Tools.

Interfaz similar a airtable.py para facilitar la migración de páginas:
  get_all_records(table_key)   → list[dict]
  get_record_by_id(table_key, record_id) → dict | None
  create_record(table_key, fields) → int  (id del registro creado)
  update_record(table_key, record_id, fields) → None
  delete_record(table_key, record_id) → None
  upsert_records(table_key, rows, conflict_col) → int  (registros afectados)

Caching:
  get_all_records usa @st.cache_data(ttl=300) — se puede invalidar llamando
  get_all_records.clear() o clear_cache().

Clientes:
  get_client()              → cliente con anon key (para la app / UI)
  get_service_client()      → cliente con service_role key (solo para sync)
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, SUPABASE_TABLES


# ---------------------------------------------------------------------------
# Clientes (singleton por sesión de Streamlit)
# ---------------------------------------------------------------------------

def get_client() -> Client:
    """Devuelve el cliente Supabase con anon key (respeta RLS)."""
    if "_sb_client" not in st.session_state:
        st.session_state["_sb_client"] = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return st.session_state["_sb_client"]


def get_service_client() -> Client:
    """Devuelve el cliente Supabase con service_role key (bypassa RLS).

    Solo debe usarse en operaciones de sync, nunca en la UI.
    """
    if "_sb_service_client" not in st.session_state:
        st.session_state["_sb_service_client"] = create_client(
            SUPABASE_URL, SUPABASE_SERVICE_KEY
        )
    return st.session_state["_sb_service_client"]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _table(table_key: str) -> str:
    """Resuelve la clave legible al nombre real de la tabla en Postgres."""
    if table_key in SUPABASE_TABLES:
        return SUPABASE_TABLES[table_key]
    # Si ya es un nombre de tabla directo, lo devuelve tal cual
    return table_key


# ---------------------------------------------------------------------------
# Lecturas (cacheadas)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def get_all_records(
    table_key: str,
    columns: str = "*",
    filters: dict[str, Any] | None = None,
    order_by: str | None = None,
    ascending: bool = True,
) -> list[dict]:
    """Lee todos los registros de una tabla de Supabase.

    Args:
        table_key:  Clave en SUPABASE_TABLES o nombre directo de tabla.
        columns:    Columnas a seleccionar (por defecto "*").
        filters:    Dict {columna: valor} para filtros de igualdad exacta.
        order_by:   Columna por la que ordenar.
        ascending:  Dirección del ordenamiento.

    Returns:
        Lista de dicts con los registros.
    """
    tbl = _table(table_key)
    client = get_client()

    query = client.table(tbl).select(columns)

    if filters:
        for col, val in filters.items():
            query = query.eq(col, val)

    if order_by:
        query = query.order(order_by, desc=not ascending)

    response = query.execute()
    return response.data or []


@st.cache_data(ttl=300, show_spinner=False)
def get_record_by_id(table_key: str, record_id: int) -> dict | None:
    """Lee un único registro por su id (BIGINT surrogate key)."""
    tbl = _table(table_key)
    response = (
        get_client()
        .table(tbl)
        .select("*")
        .eq("id", record_id)
        .limit(1)
        .execute()
    )
    data = response.data
    return data[0] if data else None


def clear_cache() -> None:
    """Invalida el caché de todas las lecturas de Supabase."""
    get_all_records.clear()
    get_record_by_id.clear()


# ---------------------------------------------------------------------------
# Escrituras (sin caché)
# ---------------------------------------------------------------------------

def create_record(table_key: str, fields: dict[str, Any]) -> int:
    """Inserta un registro y devuelve su id (BIGINT).

    Args:
        table_key: Clave en SUPABASE_TABLES.
        fields:    Dict con los valores a insertar (snake_case).

    Returns:
        El id del registro creado.
    """
    tbl = _table(table_key)
    response = get_client().table(tbl).insert(fields).execute()
    return response.data[0]["id"]


def update_record(table_key: str, record_id: int, fields: dict[str, Any]) -> None:
    """Actualiza un registro por su id.

    Args:
        table_key:  Clave en SUPABASE_TABLES.
        record_id:  id BIGINT del registro.
        fields:     Dict con los campos a actualizar.
    """
    tbl = _table(table_key)
    get_client().table(tbl).update(fields).eq("id", record_id).execute()


def delete_record(table_key: str, record_id: int) -> None:
    """Elimina un registro por su id.

    Args:
        table_key:  Clave en SUPABASE_TABLES.
        record_id:  id BIGINT del registro.
    """
    tbl = _table(table_key)
    get_client().table(tbl).delete().eq("id", record_id).execute()


def upsert_records(
    table_key: str,
    rows: list[dict[str, Any]],
    conflict_col: str = "airtable_id",
    use_service_role: bool = False,
) -> int:
    """Upsert en lote. Inserta o actualiza según conflict_col.

    Usado principalmente por el motor de sync. Por defecto usa el cliente
    anon; para operaciones de sync pasá use_service_role=True.

    Args:
        table_key:        Clave en SUPABASE_TABLES.
        rows:             Lista de dicts a upsertear.
        conflict_col:     Columna de conflicto (default: "airtable_id").
        use_service_role: Si True, usa el service_role client.

    Returns:
        Cantidad de filas afectadas.
    """
    if not rows:
        return 0

    tbl = _table(table_key)
    client = get_service_client() if use_service_role else get_client()

    # Supabase-py acepta listas en upsert; hacer en chunks de 500 para
    # evitar límites de tamaño de payload
    chunk_size = 500
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        response = (
            client.table(tbl)
            .upsert(chunk, on_conflict=conflict_col)
            .execute()
        )
        total += len(response.data or [])

    return total


# ---------------------------------------------------------------------------
# Auth helpers (para core/auth.py)
# ---------------------------------------------------------------------------

def get_user_profile(user_id: str) -> dict | None:
    """Lee el perfil de un usuario por su UUID (auth.users.id)."""
    tbl = _table("user_profiles")
    response = (
        get_client()
        .table(tbl)
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    data = response.data
    return data[0] if data else None


def get_tool_permissions(user_id: str) -> dict[str, bool]:
    """Devuelve {tool_slug: can_access} para el usuario dado."""
    tbl = _table("user_tool_permissions")
    response = (
        get_client()
        .table(tbl)
        .select("tool_slug, can_access")
        .eq("user_id", user_id)
        .execute()
    )
    return {row["tool_slug"]: row["can_access"] for row in (response.data or [])}
