# JS Tools 🏗️

Panel de herramientas internas para **JS Construcciones** — construido con Streamlit.

## Herramientas disponibles

| Herramienta | Descripción |
|---|---|
| 🧾 Verificador de Facturas | Verifica facturas de proveedores (PDF) contra registros de Airtable |

## Setup local

```bash
# 1. Clonar e instalar dependencias
git clone <repo-url>
cd js-tools
pip install -r requirements.txt

# 2. Configurar secretos
cp .env.example .env
# Editar .env con tu API key de Airtable

# 3. Ejecutar
streamlit run app.py
```

## Deploy en Streamlit Community Cloud

1. Subir el repositorio a GitHub.
2. Ir a [share.streamlit.io](https://share.streamlit.io) y conectar el repo.
3. En **Settings → Secrets**, agregar:
   ```toml
   AIRTABLE_API_KEY = "pat..."
   ```
4. El archivo principal es `app.py`.

## Agregar una nueva herramienta

1. Crear un archivo en `pages/` con prefijo numérico (ej. `pages/02_mi_herramienta.py`).
2. Definir la constante `TOOL` al inicio del archivo:
   ```python
   from core.base_tool import ToolMetadata

   TOOL = ToolMetadata(
       name="Mi Herramienta",
       description="Descripción breve de lo que hace.",
       icon="🔧",
       page_file="02_mi_herramienta.py",
   )
   ```
3. Escribir la UI de Streamlit debajo. **No** llamar a `st.set_page_config()`.
4. Reiniciar la app — la herramienta aparece automáticamente en el menú y en la página de inicio.

## Estructura del proyecto

```
app.py                  # Página de inicio + navegación
config.py               # Secretos y configuración de Airtable
requirements.txt
core/
  base_tool.py          # Dataclass ToolMetadata
  registry.py           # Auto-descubrimiento de herramientas (AST)
connectors/
  airtable.py           # Conector Airtable con traducción de field IDs
parsers/
  pdf_parser.py         # Extracción de columnas de PDFs
generators/
  pdf_generator.py      # Generación de reportes PDF
pages/
  01_verificador_facturas.py  # Verificador de facturas
```

## Troubleshooting

| Problema | Solución |
|---|---|
| "Secreto no encontrado" | Verificar que `.env` exista y tenga `AIRTABLE_API_KEY` |
| "Error al conectar con Airtable" | Verificar API key y permisos del token |
| "No se encontró la columna" | El PDF debe tener tablas con la columna "Factura Fiscal" |
| Herramienta no aparece en el menú | El archivo debe empezar con un número y tener la constante `TOOL` |
