"""Extraction agent — Phase 1.

Extracts raw schema metadata from source databases and writes to JSON output.
Migrated from root ``extractor.py``.

Public API
----------
- ``main()``
    CLI entry point that iterates all configured databases, extracts schema
    metadata, and writes the combined result to the configured JSON output
    file.
- ``extraction_node(state)``
    LangGraph-compatible pipeline node (placeholder — raises
    :exc:`NotImplementedError` until Phase 1 rework).
- ``extract_postgres_schema(creds, rules)``
    Connect to a PostgreSQL database and return column / view metadata.
- ``extract_mysql_schema(creds, rules)``
    Connect to a MySQL database and return column / relationship metadata.
"""

from __future__ import annotations

import json

import mysql.connector
import psycopg2

from etl_enrichment_pipeline.config.config_global import (
    CONNECTOR_SETTINGS,
    GLOBAL_PIPELINE,
)
from etl_enrichment_pipeline.config.config_mysql import MYSQL_DBS
from etl_enrichment_pipeline.config.config_postgres import POSTGRES_DBS

# Combine all imported database configs into one master list
ALL_DATABASES = POSTGRES_DBS + MYSQL_DBS
OUTPUT_FILE = CONNECTOR_SETTINGS["output_file"]


# ---------------------------------------------------------------------------
# Helper: PostgreSQL schema extraction
# ---------------------------------------------------------------------------

def extract_postgres_schema(creds: dict, rules: dict) -> dict:
    """Connect to a PostgreSQL database and extract schema metadata.

    Parameters
    ----------
    creds :
        Connection parameters (host, port, database, username, password).
    rules :
        Extraction-rules dict with boolean flags such as
        ``extract_table_info`` and ``extract_ddl_views``.

    Returns
    -------
    dict
        Keys ``columns`` (list), ``views`` (list), ``relationships`` (empty
        list — placeholder for future use).
    """
    result: dict[str, list[dict]] = {
        "columns": [],
        "views": [],
        "relationships": [],
    }
    conn = psycopg2.connect(**creds)
    cursor = conn.cursor()

    if rules.get("extract_table_info"):
        cursor.execute("""
            SELECT table_name, column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema='public';
        """)
        for table_name, column_name, data_type, max_length in cursor.fetchall():
            result["columns"].append({
                "table_name": table_name,
                "column_name": column_name,
                "data_type": data_type,
                "max_length": max_length,
            })

    if rules.get("extract_ddl_views"):
        cursor.execute("""
            SELECT table_name, view_definition
            FROM information_schema.views
            WHERE table_schema='public';
        """)
        for view_name, definition in cursor.fetchall():
            result["views"].append({
                "view_name": view_name,
                "definition": definition,
            })

    conn.close()
    return result


# ---------------------------------------------------------------------------
# Helper: MySQL schema extraction
# ---------------------------------------------------------------------------

def extract_mysql_schema(creds: dict, rules: dict) -> dict:
    """Connect to a MySQL database and extract schema metadata.

    Parameters
    ----------
    creds :
        Connection parameters (host, port, database, username, password).
    rules :
        Extraction-rules dict with boolean flags such as
        ``extract_table_info`` and ``extract_relations``.

    Returns
    -------
    dict
        Keys ``columns`` (list), ``relationships`` (list), ``views`` (empty
        list — placeholder for future use).
    """
    result: dict[str, list[dict]] = {
        "columns": [],
        "views": [],
        "relationships": [],
    }
    conn = mysql.connector.connect(**creds)
    cursor = conn.cursor()

    if rules.get("extract_table_info"):
        cursor.execute(f"""
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='{creds["database"]}';
        """)
        for table_name, column_name, data_type, max_length in cursor.fetchall():
            result["columns"].append({
                "table_name": table_name,
                "column_name": column_name,
                "data_type": data_type,
                "max_length": max_length,
            })

    if rules.get("extract_relations"):
        cursor.execute(f"""
            SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME,
                   REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE REFERENCED_TABLE_NAME IS NOT NULL
            AND TABLE_SCHEMA='{creds["database"]}';
        """)
        for source_table, source_column, target_table, target_column in (
            cursor.fetchall()
        ):
            result["relationships"].append({
                "source_table": source_table,
                "source_column": source_column,
                "target_table": target_table,
                "target_column": target_column,
            })

    conn.close()
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point — preserves the original root ``extractor.py`` behavior.

    Iterates all configured databases, extracts schema metadata via the
    appropriate helper, and writes the combined result to the configured JSON
    output file.
    """
    print("=======================================")
    print(">>> STARTING ETL ENRICHMENT PIPELINE (JSON MODE)")
    print("=======================================\n")

    # Master dictionary to hold the entire pipeline's output
    master_json_data: dict = {
        "metadata": {
            "environment": GLOBAL_PIPELINE["environment"],
            "status": "success",
        },
        "systems": {},
    }

    for db in ALL_DATABASES:
        system_name = db["system_name"]
        print(f"Connecting to: {system_name} [{db['db_type'].upper()}]")

        # Initialize the JSON structure for this specific database
        system_data = master_json_data["systems"][system_name] = {
            "database_type": db["db_type"],
            "columns": [],
            "views": [],
            "relationships": [],
        }

        db_type = db["db_type"]
        creds = db["credentials"]
        rules = db["extraction_rules"]

        try:
            if db_type == "postgres":
                extracted = extract_postgres_schema(creds, rules)
                system_data["columns"] = extracted["columns"]
                system_data["views"] = extracted["views"]
                print("   [OK] Postgres Extraction Complete.\n")

            elif db_type == "mysql":
                extracted = extract_mysql_schema(creds, rules)
                system_data["columns"] = extracted["columns"]
                system_data["relationships"] = extracted["relationships"]
                print("   [OK] MySQL Extraction Complete.\n")

        except Exception as e:
            print(f"   [!] FAILED to connect or extract from {system_name}.")
            print(f"       Error Details: {e}\n")
            system_data["error"] = str(e)

    # Dump the completed dictionary into a formatted JSON file
    with open(OUTPUT_FILE, "w") as json_file:
        json.dump(master_json_data, json_file, indent=4)

    print("=======================================")
    print(f"*** PIPELINE FINISHED. JSON saved to '{OUTPUT_FILE}'.")
    print("=======================================")


# ---------------------------------------------------------------------------
# LangGraph node placeholder (Phase 2)
# ---------------------------------------------------------------------------

def extraction_node(state: dict) -> dict:
    """LangGraph-compatible pipeline node — Phase 2 placeholder.

    This function will eventually drive the extraction step within a
    LangGraph workflow, accepting a ``PipelineState`` dict and returning
    the enriched state with extraction results populated.

    Parameters
    ----------
    state :
        Current pipeline state dictionary.

    Returns
    -------
    dict
        Updated pipeline state dictionary.

    Raises
    ------
    NotImplementedError
        This node needs Phase 1 rework before it can be used in the
        LangGraph pipeline.
    """
    raise NotImplementedError(
        "extraction_node() requires Phase 1 rework before it can be "
        "used in the LangGraph pipeline."
    )


if __name__ == "__main__":
    main()
