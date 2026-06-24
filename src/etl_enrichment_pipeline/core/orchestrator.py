"""Orchestrator — high-level entry points for running the enrichment pipeline.

Provides two bridge functions that connect extraction agents (DDL parser and
live database extraction) to the core LangGraph pipeline runner.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from etl_enrichment_pipeline.agents.ddl_parser import ddl_to_json
from etl_enrichment_pipeline.agents.extraction_agent import extract_postgres_schema
from etl_enrichment_pipeline.config.config_postgres import POSTGRES_DBS
from etl_enrichment_pipeline.core.pipeline import run_pipeline_from_raw_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQL file → pipeline
# ---------------------------------------------------------------------------


def run_pipeline_from_sql(
    sql_file: str,
    database_type: str = "postgresql",
    schema: str = "public",
    output_dir: str = "sqlj_son",
) -> dict[str, Any]:
    """Parse a SQL DDL file and run the full enrichment pipeline.

    Steps
    -----
    1. Parse the SQL file into raw metadata JSON via :func:`ddl_to_json`.
    2. Persist the intermediate JSON to ``{output_dir}/raw_from_ddl_{basename}.json``.
    3. Feed the raw JSON into :func:`run_pipeline_from_raw_json`.
    4. Return the enriched output dict.

    Parameters
    ----------
    sql_file :
        Path to the ``.sql`` file containing ``CREATE TABLE`` statements.
    database_type :
        Database vendor identifier (default ``"postgresql"``).
    schema :
        Database schema name (default ``"public"``).
    output_dir :
        Directory for intermediate JSON output (default ``"sqlj_son"``).

    Returns
    -------
    dict[str, Any]
        The fully enriched output in the master plan final-output format.
    """
    sql_path = Path(sql_file)
    basename = sql_path.stem
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    intermediate_path = str(out_dir / f"raw_from_ddl_{basename}.json")

    logger.info("Parsing SQL file: %s", sql_file)
    raw_json = ddl_to_json(
        filepath=sql_file,
        database_type=database_type,
        schema=schema,
        output_path=intermediate_path,
    )
    logger.info("Intermediate JSON written to: %s", intermediate_path)

    source_label = f"ddl:{basename}"
    return run_pipeline_from_raw_json(raw_json, source_label=source_label)


# ---------------------------------------------------------------------------
# Live database → pipeline
# ---------------------------------------------------------------------------


def run_pipeline_from_db(
    system_name: str,
    output_dir: str = "sqlj_son",
) -> dict[str, Any]:
    """Extract schema from a live PostgreSQL database and run the enrichment pipeline.

    Steps
    -----
    1. Look up the database config in :data:`POSTGRES_DBS` by ``system_name``.
    2. Call :func:`extract_postgres_schema` with the matched credentials and rules.
    3. Persist the intermediate JSON to ``{output_dir}/raw_from_db_{system_name}.json``.
    4. Feed the raw JSON into :func:`run_pipeline_from_raw_json`.
    5. Return the enriched output dict.

    Parameters
    ----------
    system_name :
        The ``system_name`` key in :data:`POSTGRES_DBS` to extract from.
    output_dir :
        Directory for intermediate JSON output (default ``"sqlj_son"``).

    Returns
    -------
    dict[str, Any]
        The fully enriched output in the master plan final-output format.

    Raises
    ------
    ValueError
        If no database configuration is found for ``system_name``.
    """
    # Look up the database config by system_name
    db_config = None
    for db in POSTGRES_DBS:
        if db["system_name"] == system_name:
            db_config = db
            break

    if db_config is None:
        available = [d["system_name"] for d in POSTGRES_DBS]
        msg = (
            f"No PostgreSQL configuration found for system_name={system_name!r}. "
            f"Available systems: {available}"
        )
        logger.error(msg)
        raise ValueError(msg)

    creds = db_config["credentials"]
    rules = db_config["extraction_rules"]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    intermediate_path = out_dir / f"raw_from_db_{system_name}.json"

    logger.info("Extracting schema from database: %s", system_name)
    raw_json = extract_postgres_schema(creds, rules)

    # Persist the intermediate JSON to disk
    intermediate_path.write_text(
        json.dumps(raw_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Intermediate JSON written to: %s", intermediate_path)

    source_label = f"db:{system_name}"
    return run_pipeline_from_raw_json(raw_json, source_label=source_label)


__all__ = [
    "run_pipeline_from_db",
    "run_pipeline_from_sql",
]
