#!/usr/bin/env python3
"""Entry point — run the API server or execute the enrichment pipeline directly.

Usage:
    uv run main.py api               # start the enrichment API server (port 8000)
    uv run main.py nl2sql            # start the NL2SQL API server (port 8001)
    uv run main.py --sql-file <file> # run the pipeline on a metadata JSON file
    uv run main.py --db-connect      # run interactive database extraction
    uv run main.py                       # start the enrichment API server (default)
    uv run main.py api                   # same as above
    uv run main.py nl2sql               # start the NL2SQL API server (port 8001)
    uv run main.py pipeline <file>       # run the pipeline on a metadata JSON file
    uv run main.py --sql-file <path>     # run the pipeline from a SQL DDL file
    uv run main.py --db-connect <name>   # run the pipeline from a live database

For uvicorn directly:
    uv run uvicorn main:app              # enrichment API (port 8000)
    uv run uvicorn src.etl_enrichment_pipeline.api.nl2sql_app:app --port 8001  # NL2SQL
"""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import sys
from pathlib import Path

import yaml

from etl_enrichment_pipeline.api.main import app as _app
from etl_enrichment_pipeline.core.orchestrator import run_pipeline_from_db, run_pipeline_from_sql
from etl_enrichment_pipeline.core.pipeline import run_pipeline as _run_pipeline
from etl_enrichment_pipeline.core.pipeline import run_pipeline_from_dict
from etl_enrichment_pipeline.agents.extraction_agent import run_extraction_flow


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger so pipeline node logs appear on stderr."""
    try:
        from etl_enrichment_pipeline.config.config_global import GLOBAL_PIPELINE
        level = GLOBAL_PIPELINE.get("log_level", level).upper()
    except Exception:
        pass

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

# ---------------------------------------------------------------
# Exposed for:  uv run uvicorn main:app
# ---------------------------------------------------------------
app = _app


def run_api() -> None:
    setup_logging()
    import uvicorn

    uvicorn.run(
        "src.etl_enrichment_pipeline.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


def run_nl2sql_api() -> None:
    """Start the standalone NL2SQL API server on port 8001."""
    setup_logging()
    import uvicorn

    uvicorn.run(
        "src.etl_enrichment_pipeline.api.nl2sql_app:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )


def run_pipeline_file(file_path: str = "sql_json/raw_metadata.json") -> None:
    setup_logging()
    result = _run_pipeline(file_path)
    _save_output(result)


def run_pipeline_db(creds: dict, db_type: str) -> None:
    setup_logging()
    
    # 1. Extract metadata dictionary directly
    schema_dict = run_extraction_flow(db_type, creds)
    
    # 2. Pass dictionary directly to pipeline (no disk reload)
    result = run_pipeline_from_dict(schema_dict)
    _save_output(result)


def _save_output(result: dict) -> None:
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    out_path = out_dir / "enriched_metadata.json"
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"Written to {out_path}")


def interactive_db_flow(extract_only: bool = False) -> None:
    print("\n--- Database Connection ---")
    db_type = input("Database Type (postgres, mysql, mariadb, sqlserver, oracle, sqlite): ").strip().lower()
    
    # Load config file for defaults if it exists
    config_path = Path("config") / f"{db_type}.yaml"
    config_defaults = {}
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config_defaults = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load config {config_path}: {e}")
            
    default_port = config_defaults.get("default_port", "")
    
    host = input("Host (e.g. localhost): ").strip()
    
    port_prompt = f"Port ({default_port}): " if default_port else "Port: "
    port = input(port_prompt).strip()
    if not port and default_port:
        port = str(default_port)
        
    database = input("Database Name: ").strip()
    
    creds = {
        "host": host,
        "database": database
    }
    
    if port:
        creds["port"] = port
        
    if db_type != "sqlite":
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        creds["username"] = username
        creds["password"] = password
        
    # Filter out our internal keys before passing to creds
    for k, v in config_defaults.items():
        if k not in ["default_port", "driver"]:
            if k not in creds or not creds[k]:
                creds[k] = v
            
    if extract_only:
        setup_logging()
        run_extraction_flow(db_type, creds)
        print("\n[OK] Extraction complete! The schema JSON is saved in the 'sql_json' directory.")
    else:
        run_pipeline_db(creds, db_type)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ETL Schema Intelligence — API server or CLI pipeline runner",
    )

    # Flags (mutually-exclusive with the pipeline subcommand)
    parser.add_argument(
        "--sql-file",
        type=str,
        help="Path to a SQL DDL file to parse and enrich",
        metavar="PATH",
    )
    parser.add_argument(
        "--db-connect",
        action="store_true",
        help="Launch interactive database connection flow",
    )

    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Only extract the database schema (skip the AI pipeline)",
    )

    parser.add_argument(
        "command",
        nargs="?",
        default=None,
        choices=("api", "nl2sql", "pipeline"),
        help="Subcommand (api, nl2sql, or pipeline)",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="sql_json/raw_metadata.json",
        help="Path to raw metadata JSON (pipeline command only)",
    )

    args = parser.parse_args()

    # --sql-file: parse SQL DDL and run pipeline
    if args.sql_file:
        sql_path = Path(args.sql_file)
        if not sql_path.exists():
            parser.error(f"--sql-file: {args.sql_file!r} does not exist")
        setup_logging()
        result = run_pipeline_from_sql(str(sql_path))
        _save_output(result)
        return

    # --db-connect: interactive database connection
    if args.db_connect:
        interactive_db_flow(extract_only=args.extract_only)
        return

    # Positional subcommand
    if args.command == "pipeline":
        run_pipeline_file(args.file)
        return

    # Enrichment API server (explicit "api" subcommand or no args at all)
    if args.command == "api" or (args.command is None and not args.sql_file and not args.db_connect):
        run_api()
        return

    # NL2SQL API server (separate process on port 8001)
    if args.command == "nl2sql":
        run_nl2sql_api()
        return

    # Interactive Terminal Flow
    print("\nSelect Action:")
    print("1. Run AI Pipeline from SQL File")
    print("2. Run AI Pipeline from Database Connection")
    print("3. Extract Database Schema Only (Save JSON)")
    
    choice = input("Enter choice (1/2/3): ").strip()
    
    if choice == "1":
        filepath = input("Enter path to JSON file (default: sql_json/raw_metadata.json): ").strip()
        if not filepath:
            filepath = "sql_json/raw_metadata.json"
        run_pipeline_file(filepath)
    elif choice == "2":
        interactive_db_flow(extract_only=False)
    elif choice == "3":
        interactive_db_flow(extract_only=True)
    else:
        print("Invalid choice. Exiting.")


if __name__ == "__main__":
    main()
