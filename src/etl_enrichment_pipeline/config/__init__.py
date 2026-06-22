"""Global and per-source configuration dictionaries."""

from etl_enrichment_pipeline.config.config_global import (
    CONNECTOR_SETTINGS,
    GLOBAL_PIPELINE,
)
from etl_enrichment_pipeline.config.config_mysql import MYSQL_DBS
from etl_enrichment_pipeline.config.config_postgres import POSTGRES_DBS

__all__ = ["GLOBAL_PIPELINE", "CONNECTOR_SETTINGS", "POSTGRES_DBS", "MYSQL_DBS"]
