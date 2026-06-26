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
from etl_enrichment_pipeline.core.pipeline import run_pipeline_from_raw_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQL file → pipeline
# ---------------------------------------------------------------------------


def run_pipeline_from_sql(
    sql_file: str,
    database_type: str = "postgresql",
    schema: str = "public",
    output_dir: str = "sql_json",
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


__all__ = [
    "run_pipeline_from_sql",
]
