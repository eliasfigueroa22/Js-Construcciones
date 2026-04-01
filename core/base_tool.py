"""Dataclass base para metadatos de herramientas."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolMetadata:
    """Metadatos de una herramienta del panel.

    Cada página en pages/ define una constante TOOL = ToolMetadata(...)
    que el registry lee vía AST sin ejecutar el archivo.
    """

    name: str
    description: str
    icon: str
    page_file: str
