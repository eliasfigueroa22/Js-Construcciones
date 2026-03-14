"""
Configuration for Airtable → DuckDB extraction.

Table IDs must be set in a .env file at the project root.
The AIRTABLE_TABLES mapping links each Airtable table ID
to the raw table name it will have in DuckDB.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

AIRTABLE_API_TOKEN = os.getenv("AIRTABLE_API_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")    
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "v2_analytics/warehouse/js_construcciones.duckdb")

# Resolve relative DuckDB path against project root
if not os.path.isabs(DUCKDB_PATH):
    DUCKDB_PATH = str(PROJECT_ROOT / DUCKDB_PATH)

# -----------------------------------------------------------------
# Airtable table ID → DuckDB raw table name

AIRTABLE_TABLES = {
    # Fact tables
    "tbl47ExnBN9stlzlW": "fact_compra",
    "tblTNEawQcaBtN76b": "fact_pago",
    "tblyF7UraXgsqrGDO": "fact_ingreso",
    "tblrmoDOxyYODIYHl": "fact_deuda",
    "tblWzMK0j1vV7cldl": "fact_pago_deuda",
    "tbl7K2uE74waZ6Hu5": "fact_presupuesto_cliente",
    "tblxeg6cYjNFJYONv": "fact_presupuesto_subcontratista",
    "tblEk7Btplj6WZSyr": "fact_facturacion_subcontratista",
    "tbl9kD1iGC1m42Z1O": "fact_compras_personal",
    # Dimension tables
    "tbldULscM4zk2oPBu": "dim_obras",
    "tblkZ3FHekPCk651F": "dim_clientes",
    "tbl5N8FMH2Yk5HZ1H": "dim_proveedores",
    "tblBnkW8rTrYc1GTA": "dim_proveedores_personal",
    "tblgBuKAq7z8N7wgu": "dim_trabajador",
    "tblusMPTyS1CivZM5": "dim_rubro",
    "tblWIKPSI9QLoQovC": "dim_sector"
}
