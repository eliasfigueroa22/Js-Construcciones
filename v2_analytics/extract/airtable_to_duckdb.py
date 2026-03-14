"""
Extract all Airtable tables into DuckDB (raw schema).

Usage:
    python -m v2_analytics.extract.airtable_to_duckdb

Full refresh every run — drops and recreates each raw table.
Adds _extracted_at timestamp to every row.

Uses the Airtable metadata API to get the full schema of each table,
so columns that exist but have no data are still created in DuckDB.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests
from pyairtable import Api

from v2_analytics.extract.config import (
    AIRTABLE_API_TOKEN,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLES,
    DUCKDB_PATH,
)


def get_table_fields(base_id: str, table_id: str, api_token: str) -> list[str]:
    """Fetch the full list of field names from Airtable's metadata API."""
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    for table in response.json()["tables"]:
        if table["id"] == table_id:
            return [
                f["name"]
                for f in table["fields"]
                if not f["name"].startswith("_")
            ]
    return []


def extract_table(api: Api, base_id: str, table_id: str, all_fields: list[str]) -> pd.DataFrame:
    """Fetch all records from one Airtable table and return as DataFrame.

    Uses all_fields from the metadata API to ensure every column exists
    in the resulting DataFrame, even if no record has data for it.
    """
    table = api.table(base_id, table_id)
    records = table.all()

    rows = []
    for record in records:
        row = {"airtable_id": record["id"]}
        for key, value in record["fields"].items():
            # Skip linked record columns (prefixed with _)
            if key.startswith("_"):
                continue
            # Airtable linked records come as lists — take first value
            if isinstance(value, list):
                value = value[0] if value else None
            row[key] = value
        rows.append(row)

    df = pd.DataFrame(rows)

    # Ensure all schema columns exist, even if empty
    for field in all_fields:
        if field not in df.columns:
            df[field] = None

    df["_extracted_at"] = datetime.now(timezone.utc)
    return df


def load_to_duckdb(con: duckdb.DuckDBPyConnection, df: pd.DataFrame, table_name: str) -> int:
    """Load a DataFrame into DuckDB raw schema (full refresh)."""
    con.execute(f"DROP TABLE IF EXISTS raw.{table_name}")
    con.execute(f"CREATE TABLE raw.{table_name} AS SELECT * FROM df")
    result = con.execute(f"SELECT count(*) FROM raw.{table_name}").fetchone()
    return result[0]


def main():
    if not AIRTABLE_API_TOKEN or not AIRTABLE_BASE_ID:
        print("ERROR: Set AIRTABLE_API_TOKEN and AIRTABLE_BASE_ID in .env")
        sys.exit(1)

    # Ensure warehouse directory exists
    Path(DUCKDB_PATH).parent.mkdir(parents=True, exist_ok=True)

    api = Api(AIRTABLE_API_TOKEN)
    con = duckdb.connect(DUCKDB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    print(f"Extracting {len(AIRTABLE_TABLES)} tables from Airtable → DuckDB")
    print(f"Database: {DUCKDB_PATH}\n")

    total_rows = 0
    for table_id, table_name in AIRTABLE_TABLES.items():
        try:
            all_fields = get_table_fields(AIRTABLE_BASE_ID, table_id, AIRTABLE_API_TOKEN)
            df = extract_table(api, AIRTABLE_BASE_ID, table_id, all_fields)
            rows = load_to_duckdb(con, df, table_name)
            total_rows += rows
            print(f"  ✓ {table_name:<45} {rows:>6} rows  ({len(df.columns) - 2} fields)")
        except Exception as e:
            print(f"  ✗ {table_name:<45} ERROR: {e}")

    con.close()
    print(f"\nDone. {total_rows} total rows loaded into raw schema.")


if __name__ == "__main__":
    main()
