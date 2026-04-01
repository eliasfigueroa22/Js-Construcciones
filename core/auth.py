"""Capa de autenticación para JS Tools.

Usa Supabase Auth (email/password).
El estado de sesión se guarda en st.session_state["_auth"].

Uso en cada página (o en app.py):
    from core.auth import require_auth
    require_auth()   # redirige a login si no hay sesión activa

Funciones exportadas:
    require_auth()            → None (o st.stop())
    get_current_user()        → dict | None
    get_current_role()        → str | None  ('admin'|'operador'|'viewer')
    get_tool_permissions()    → dict[str, bool]
    has_tool_access(slug)     → bool
    logout()                  → None
"""

from __future__ import annotations

import streamlit as st
from supabase import AuthApiError

from config import SUPABASE_URL, SUPABASE_ANON_KEY
from connectors.supabase_connector import get_client, get_user_profile, get_tool_permissions as _fetch_perms

# Clave en session_state donde guardamos el estado de auth
_AUTH_KEY = "_auth"

# Slugs de todas las herramientas
ALL_TOOL_SLUGS = [
    "verificador_facturas",
    "resumen_pagos",
    "gestor_duplicados",
    "reporte_obra",
    "mediciones",
    "certificaciones",
    "planilla_pagos",
]


# ---------------------------------------------------------------------------
# Helpers de sesión
# ---------------------------------------------------------------------------

def _get_session() -> dict | None:
    return st.session_state.get(_AUTH_KEY)


def _set_session(user_id: str, email: str, access_token: str) -> None:
    profile = get_user_profile(user_id) or {}
    perms = _fetch_perms(user_id)
    st.session_state[_AUTH_KEY] = {
        "user_id":     user_id,
        "email":       email,
        "access_token":access_token,
        "nombre":      profile.get("nombre", email),
        "role":        profile.get("role", "viewer"),
        "activo":      profile.get("activo", True),
        "perms":       perms,   # {tool_slug: bool}
    }


def _clear_session() -> None:
    st.session_state.pop(_AUTH_KEY, None)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def get_current_user() -> dict | None:
    """Devuelve el dict de sesión o None si no hay sesión activa."""
    return _get_session()


def get_current_role() -> str | None:
    """Devuelve el rol del usuario autenticado ('admin'|'operador'|'viewer')."""
    s = _get_session()
    return s["role"] if s else None


def get_tool_permissions() -> dict[str, bool]:
    """Devuelve {tool_slug: can_access} del usuario actual.

    Los admin tienen acceso a todo sin necesidad de registros en
    user_tool_permissions.
    """
    s = _get_session()
    if not s:
        return {slug: False for slug in ALL_TOOL_SLUGS}
    if s["role"] == "admin":
        return {slug: True for slug in ALL_TOOL_SLUGS}
    return s.get("perms", {})


def has_tool_access(tool_slug: str) -> bool:
    """True si el usuario actual tiene acceso a la herramienta dada."""
    return get_tool_permissions().get(tool_slug, False)


def logout() -> None:
    """Cierra sesión y limpia el estado."""
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    _clear_session()
    st.rerun()


# ---------------------------------------------------------------------------
# Login UI
# ---------------------------------------------------------------------------

def _render_login() -> None:
    """Renderiza el formulario de login centrado en la pantalla."""
    st.markdown(
        """
        <style>
        .login-wrap { max-width: 400px; margin: 80px auto 0; }
        .login-title { font-size: 1.6rem; font-weight: 700;
                       color: #E8622A; margin-bottom: 4px; }
        .login-sub   { color: #6B7280; font-size: .9rem; margin-bottom: 24px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">JS Tools</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-sub">JS Construcciones — Panel de Administración</div>',
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            email    = st.text_input("Correo electrónico", placeholder="usuario@jsconst.com")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Completá ambos campos.")
                return
            try:
                client = get_client()
                resp = client.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                user = resp.user
                session = resp.session
                if not user or not session:
                    st.error("Credenciales inválidas.")
                    return

                profile = get_user_profile(user.id)
                if not profile:
                    st.error("Usuario no encontrado en el sistema. Contactá al admin.")
                    return
                if not profile.get("activo", True):
                    st.error("Tu cuenta está desactivada. Contactá al admin.")
                    return

                _set_session(user.id, user.email, session.access_token)
                st.rerun()

            except AuthApiError as exc:
                st.error(f"Error de autenticación: {exc.message}")
            except Exception as exc:
                st.error(f"Error inesperado: {exc}")

        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Gate principal
# ---------------------------------------------------------------------------

def require_auth() -> None:
    """Verifica que haya una sesión activa. Si no, muestra login y detiene.

    Llamar al inicio de app.py (antes de st.navigation).
    """
    session = _get_session()
    if session is None:
        st.set_page_config(
            page_title="JS Tools — Iniciar Sesión",
            page_icon="🔐",
            layout="centered",
        )
        _render_login()
        st.stop()
