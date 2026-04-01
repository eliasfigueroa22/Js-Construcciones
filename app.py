"""JS Tools — Panel de herramientas internas de JS Construcciones."""

import streamlit as st

from core.auth import require_auth, get_current_user, get_current_role, get_tool_permissions, logout
from core.registry import get_all_tools
from connectors.sync import run_full_sync
from connectors.supabase_connector import clear_cache, get_all_records

# Auth gate — si no hay sesión, muestra login y hace st.stop()
# (set_page_config se llama dentro de require_auth cuando no hay sesión;
# si hay sesión, lo llamamos nosotros aquí abajo)
_session = get_current_user()
if _session is None:
    require_auth()

st.set_page_config(page_title="JS Tools", page_icon="🏗️", layout="wide")

all_tools = get_all_tools()
tool_perms = get_tool_permissions()
role = get_current_role()

# Filtrar herramientas según permisos del usuario
# page_file → tool_slug: "01_verificador_facturas.py" → "verificador_facturas"
def _slug(page_file: str) -> str:
    return "_".join(page_file.split("_")[1:]).replace(".py", "")

visible_tools = [t for t in all_tools if tool_perms.get(_slug(t.page_file), False)]

# -- Sidebar ------------------------------------------------------------------
with st.sidebar:
    user = get_current_user()
    st.markdown(f"**{user['nombre']}**")
    st.caption(f"Rol: {role}")
    st.divider()

    # Sync desde Airtable
    st.caption("Base de datos")
    if st.button("🔄 Sincronizar desde Airtable", use_container_width=True,
                 help="Importa los últimos datos de Airtable a Supabase"):
        with st.spinner("Sincronizando..."):
            result = run_full_sync()
        if result["status"] == "success":
            st.success(f"✓ {result['total']:,} registros actualizados")
        elif result["status"] == "partial":
            st.warning(f"Parcial — {result['total']:,} registros. Ver errores abajo.")
            for err in result["errors"][:5]:
                st.caption(f"⚠ {err}")
        else:
            st.error("Sync fallido.")
            for err in result["errors"][:5]:
                st.caption(f"✗ {err}")

    # Último sync
    try:
        logs = get_all_records(
            "aux_sync_log",
            columns="table_name, finished_at, records_upserted, status",
            filters={"table_name": "__full_sync__"},
            order_by="started_at",
            ascending=False,
        )
        if logs:
            last = logs[0]
            if last.get("finished_at"):
                from datetime import datetime
                ts = last["finished_at"][:16].replace("T", " ")
                st.caption(f"Último sync: {ts}")
    except Exception:
        pass

    st.divider()

    if st.button("🚪 Cerrar sesión", use_container_width=True):
        logout()


# -- Páginas ------------------------------------------------------------------
def home_page():
    """Página de inicio con tarjetas de herramientas disponibles."""
    st.title("JS Tools")
    st.caption("Panel de herramientas internas — JS Construcciones")

    if not visible_tools:
        st.info("No tenés herramientas habilitadas. Contactá al administrador.")
        return

    cols = st.columns(min(len(visible_tools), 3))
    for i, tool in enumerate(visible_tools):
        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(f"{tool.icon} {tool.name}")
                st.write(tool.description)
                st.page_link(
                    f"pages/{tool.page_file}",
                    label="Abrir herramienta →",
                    use_container_width=True,
                )


pages = [st.Page(home_page, title="Inicio", icon="🏠", default=True)]
for tool in visible_tools:
    pages.append(
        st.Page(f"pages/{tool.page_file}", title=tool.name, icon=tool.icon)
    )

pg = st.navigation(pages)
pg.run()
