"""Extraction agent — Phase 1.

Extracts raw schema metadata from source databases and returns it as a dictionary.
Can be invoked by the CLI to write JSON and return the dict directly.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_schema_generic(db_type: str, creds: dict) -> dict:
    """Dynamically connects to the database based on db_type and extracts schema."""
    logger.info(f"Starting metadata extraction for {db_type}")

    if db_type == "postgres":
        data = extract_postgres_schema(creds)
    elif db_type in ("mysql", "mariadb"):
        data = extract_mysql_schema(creds)
    elif db_type == "sqlserver":
        data = extract_sqlserver_schema(creds)
    elif db_type == "oracle":
        data = extract_oracle_schema(creds)
    elif db_type == "sqlite":
        data = extract_sqlite_schema(creds)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    # Write to sql_json
    os.makedirs("sql_json", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_name = creds.get("database", "unknown")
    if db_type == "sqlite":
        db_name = os.path.basename(db_name)
    filename = f"sql_json/{db_type}_{db_name}_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Raw metadata written to {filename}")

    return data


def extract_postgres_schema(creds: dict) -> dict:
    import psycopg2

    pg_creds = creds.copy()
    if "username" in pg_creds:
        pg_creds["user"] = pg_creds.pop("username")
    conn = psycopg2.connect(**pg_creds)
    cursor = conn.cursor()

    result_tables = []

    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema='public' AND table_type='BASE TABLE';
    """)
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='{table}';
        """)
        columns = [
            {"column_name": row[0], "data_type": row[1], "nullable": row[2] == "YES"}
            for row in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT tc.constraint_name, tc.constraint_type, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public' AND tc.table_name = '{table}'
              AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE');
        """)
        constraints = [
            {
                "constraint_name": row[0],
                "constraint_type": row[1],
                "column_name": row[2],
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT kcu.column_name AS child_column, ccu.table_name AS parent_table, ccu.column_name AS parent_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public' AND tc.table_name = '{table}';
        """)
        relationships = [
            {"child_column": row[0], "parent_table": row[1], "parent_column": row[2]}
            for row in cursor.fetchall()
        ]

        result_tables.append(
            {
                "table_name": table,
                "columns": columns,
                "constraints": constraints,
                "relationships": relationships,
            }
        )

    result_views = []
    cursor.execute("""
        SELECT table_name, view_definition
        FROM information_schema.views
        WHERE table_schema='public';
    """)
    views = cursor.fetchall()
    
    for view_name, view_def in views:
        cursor.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='{view_name}';
        """)
        columns = [
            {"column_name": row[0], "data_type": row[1], "nullable": row[2] == "YES"}
            for row in cursor.fetchall()
        ]
        result_views.append({
            "view_name": view_name,
            "columns": columns,
            "definition": view_def
        })

    conn.close()
    return {"database_type": "postgresql", "schema": "public", "tables": result_tables, "views": result_views}


def extract_mysql_schema(creds: dict) -> dict:
    import pymysql  # type: ignore

    db_name = creds.get("database")
    my_creds = creds.copy()
    if "username" in my_creds:
        my_creds["user"] = my_creds.pop("username")

    conn = pymysql.connect(
        host=my_creds.get("host", "localhost"),
        port=int(my_creds.get("port", 3306)),
        user=my_creds.get("user", "root"),
        password=my_creds.get("password", ""),
        database=db_name,
    )
    cursor = conn.cursor()

    result_tables = []

    cursor.execute(f"""
        SELECT TABLE_NAME 
        FROM information_schema.tables 
        WHERE table_schema='{db_name}' AND table_type='BASE TABLE';
    """)
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM information_schema.columns
            WHERE table_schema='{db_name}' AND table_name='{table}';
        """)
        columns = [
            {"column_name": row[0], "data_type": row[1], "nullable": row[2] == "YES"}
            for row in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE, kcu.COLUMN_NAME
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA AND kcu.TABLE_NAME = tc.TABLE_NAME
            WHERE tc.table_schema = '{db_name}' AND tc.table_name = '{table}'
              AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE');
        """)
        constraints = [
            {
                "constraint_name": row[0],
                "constraint_type": row[1],
                "column_name": row[2],
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM information_schema.key_column_usage
            WHERE table_schema = '{db_name}' AND table_name = '{table}' AND referenced_table_name IS NOT NULL;
        """)
        relationships = [
            {"child_column": row[0], "parent_table": row[1], "parent_column": row[2]}
            for row in cursor.fetchall()
        ]

        result_tables.append(
            {
                "table_name": table,
                "columns": columns,
                "constraints": constraints,
                "relationships": relationships,
            }
        )

    result_views = []
    cursor.execute(f"""
        SELECT TABLE_NAME, VIEW_DEFINITION
        FROM information_schema.views
        WHERE table_schema='{db_name}';
    """)
    views = cursor.fetchall()
    
    for view_name, view_def in views:
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM information_schema.columns
            WHERE table_schema='{db_name}' AND table_name='{view_name}';
        """)
        columns = [
            {"column_name": row[0], "data_type": row[1], "nullable": row[2] == "YES"}
            for row in cursor.fetchall()
        ]
        result_views.append({
            "view_name": view_name,
            "columns": columns,
            "definition": view_def
        })

    conn.close()
    return {"database_type": "mysql", "schema": db_name, "tables": result_tables, "views": result_views}


def extract_sqlserver_schema(creds: dict) -> dict:
    import pyodbc  # type: ignore

    server = creds.get("host")
    database = creds.get("database")
    username = creds.get("username")
    password = creds.get("password")
    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    result_tables = []

    cursor.execute("""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE='BASE TABLE';
    """)
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME='{table}';
        """)
        columns = [
            {"column_name": row[0], "data_type": row[1], "nullable": row[2] == "YES"}
            for row in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE, ccu.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
              ON tc.CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = '{table}'
              AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE');
        """)
        constraints = [
            {
                "constraint_name": row[0],
                "constraint_type": row[1],
                "column_name": row[2],
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT 
                fk.name AS constraint_name,
                tp.name AS parent_table,
                cp.name AS parent_column,
                tr.name AS referenced_table,
                cr.name AS referenced_column
            FROM sys.foreign_keys fk
            INNER JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
            INNER JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
            INNER JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
            INNER JOIN sys.columns cp ON fkc.parent_column_id = cp.column_id AND fkc.parent_object_id = cp.object_id
            INNER JOIN sys.columns cr ON fkc.referenced_column_id = cr.column_id AND fkc.referenced_object_id = cr.object_id
            WHERE tp.name = '{table}';
        """)
        relationships = [
            {"child_column": row[2], "parent_table": row[3], "parent_column": row[4]}
            for row in cursor.fetchall()
        ]

        result_tables.append(
            {
                "table_name": table,
                "columns": columns,
                "constraints": constraints,
                "relationships": relationships,
            }
        )

    result_views = []
    cursor.execute("""
        SELECT TABLE_NAME, VIEW_DEFINITION
        FROM INFORMATION_SCHEMA.VIEWS;
    """)
    views = cursor.fetchall()
    
    for view_name, view_def in views:
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME='{view_name}';
        """)
        columns = [
            {"column_name": row[0], "data_type": row[1], "nullable": row[2] == "YES"}
            for row in cursor.fetchall()
        ]
        result_views.append({
            "view_name": view_name,
            "columns": columns,
            "definition": view_def
        })

    conn.close()
    return {"database_type": "sqlserver", "schema": "dbo", "tables": result_tables, "views": result_views}


def extract_oracle_schema(creds: dict) -> dict:
    import oracledb  # type: ignore

    user = creds.get("username")
    password = creds.get("password")
    host = creds.get("host")
    port = creds.get("port")
    sid = creds.get("database")
    dsn = f"{host}:{port}/{sid}"
    conn = oracledb.connect(user=user, password=password, dsn=dsn)
    cursor = conn.cursor()

    result_tables = []

    cursor.execute("SELECT TABLE_NAME FROM USER_TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, NULLABLE 
            FROM USER_TAB_COLUMNS 
            WHERE TABLE_NAME = '{table}'
        """)
        columns = [
            {"column_name": row[0], "data_type": row[1], "nullable": row[2] == "Y"}
            for row in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE 
            FROM USER_CONSTRAINTS 
            WHERE TABLE_NAME = '{table}' AND CONSTRAINT_TYPE IN ('P', 'R', 'U')
        """)
        constraints = []
        for row in cursor.fetchall():
            ctype = (
                "PRIMARY KEY"
                if row[1] == "P"
                else "FOREIGN KEY"
                if row[1] == "R"
                else "UNIQUE"
            )
            cursor.execute(
                f"SELECT COLUMN_NAME FROM USER_CONS_COLUMNS WHERE CONSTRAINT_NAME = '{row[0]}'"
            )
            col_rows = cursor.fetchall()
            for col_row in col_rows:
                constraints.append(
                    {
                        "constraint_name": row[0],
                        "constraint_type": ctype,
                        "column_name": col_row[0],
                    }
                )

        cursor.execute(f"""
            SELECT a.column_name child_column, c_pk.table_name parent_table, b.column_name parent_column
            FROM user_cons_columns a
            JOIN user_constraints c ON a.owner = c.owner AND a.constraint_name = c.constraint_name
            JOIN user_constraints c_pk ON c.r_owner = c_pk.owner AND c.r_constraint_name = c_pk.constraint_name
            JOIN user_cons_columns b ON c_pk.owner = b.owner AND c_pk.constraint_name = b.constraint_name AND a.position = b.position
            WHERE c.constraint_type = 'R' AND a.table_name = '{table}'
        """)
        relationships = [
            {"child_column": row[0], "parent_table": row[1], "parent_column": row[2]}
            for row in cursor.fetchall()
        ]

        result_tables.append(
            {
                "table_name": table,
                "columns": columns,
                "constraints": constraints,
                "relationships": relationships,
            }
        )

    result_views = []
    cursor.execute("SELECT VIEW_NAME, TEXT FROM USER_VIEWS")
    views_raw = cursor.fetchall()
    
    for row in views_raw:
        view_name = row[0]
        view_def = row[1].read() if hasattr(row[1], 'read') else row[1]
        
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, NULLABLE 
            FROM USER_TAB_COLUMNS 
            WHERE TABLE_NAME = '{view_name}'
        """)
        columns = [
            {"column_name": col_row[0], "data_type": col_row[1], "nullable": col_row[2] == "Y"}
            for col_row in cursor.fetchall()
        ]
        result_views.append({
            "view_name": view_name,
            "columns": columns,
            "definition": view_def
        })

    conn.close()
    return {"database_type": "oracle", "schema": user, "tables": result_tables, "views": result_views}


def extract_sqlite_schema(creds: dict) -> dict:
    import sqlite3
    db_path = str(creds.get("database", ""))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    result_tables = []

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall() if row[0] != "sqlite_sequence"]

    for table in tables:
        cursor.execute(f"PRAGMA table_info('{table}');")
        columns = []
        constraints = []
        for row in cursor.fetchall():
            col_name = row[1]
            data_type = row[2]
            notnull = row[3]
            pk = row[5]
            columns.append(
                {
                    "column_name": col_name,
                    "data_type": data_type,
                    "nullable": notnull == 0,
                }
            )
            if pk > 0:
                constraints.append(
                    {
                        "constraint_name": f"pk_{table}",
                        "constraint_type": "PRIMARY KEY",
                        "column_name": col_name,
                    }
                )

        cursor.execute(f"PRAGMA foreign_key_list('{table}');")
        relationships = []
        for row in cursor.fetchall():
            relationships.append(
                {
                    "child_column": row[3],
                    "parent_table": row[2],
                    "parent_column": row[4],
                }
            )

        result_tables.append(
            {
                "table_name": table,
                "columns": columns,
                "constraints": constraints,
                "relationships": relationships,
            }
        )

    result_views = []
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='view';")
    views = cursor.fetchall()
    
    for view_name, view_def in views:
        cursor.execute(f"PRAGMA table_info('{view_name}');")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                "column_name": row[1],
                "data_type": row[2],
                "nullable": row[3] == 0,
            })
            
        result_views.append({
            "view_name": view_name,
            "columns": columns,
            "definition": view_def
        })

    conn.close()
    return {"database_type": "sqlite", "schema": "main", "tables": result_tables, "views": result_views}


def run_extraction_flow(db_type: str, creds: dict) -> dict:
    """Entry point for database extraction. Saves JSON and returns dict."""
    logger.info(f"Connecting to database type: {db_type}")

    try:
        schema_dict = extract_schema_generic(db_type, creds)

        # Save to sql_json/
        os.makedirs("sql_json", exist_ok=True)
        db_name = creds.get("database", "unknown").replace("/", "_").replace("\\", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join("sql_json", f"{db_type}_{db_name}_{timestamp}.json")

        with open(output_path, "w") as f:
            json.dump(schema_dict, f, indent=2)

        logger.info(f"Metadata extraction completed. JSON saved to {output_path}")
        return schema_dict

    except Exception as e:
        logger.error(f"Failed to extract schema from {db_type}: {e}")
        raise

def extraction_node(state: dict) -> dict:
    raise NotImplementedError(
        "extraction_node() requires Phase 1 rework before it can be used in the LangGraph pipeline."
    )
