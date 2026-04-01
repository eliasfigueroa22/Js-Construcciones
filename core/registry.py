"""Registro automático de herramientas vía AST.

Escanea pages/ y extrae la constante TOOL = ToolMetadata(...) de cada archivo
sin ejecutar código. Esto evita que los widgets de Streamlit se rendericen
al importar las páginas.
"""

import ast
import logging
from pathlib import Path

from core.base_tool import ToolMetadata

logger = logging.getLogger(__name__)


def get_all_tools() -> list[ToolMetadata]:
    """Descubre herramientas en pages/ parseando AST."""
    tools: list[ToolMetadata] = []
    pages_dir = Path(__file__).resolve().parent.parent / "pages"

    if not pages_dir.is_dir():
        logger.warning("Directorio pages/ no encontrado en %s", pages_dir)
        return tools

    for py_file in sorted(pages_dir.glob("[0-9]*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "TOOL"
                        for t in node.targets
                    )
                    and isinstance(node.value, ast.Call)
                ):
                    kwargs = {
                        kw.arg: kw.value.value
                        for kw in node.value.keywords
                        if isinstance(kw.value, ast.Constant)
                    }
                    tools.append(ToolMetadata(**kwargs))
        except Exception:
            logger.warning(
                "No se pudo leer herramienta de %s", py_file.name, exc_info=True
            )

    return tools
