"""ETL Enrichment Pipeline - Core package."""

__version__ = "0.1.0"

from etl_enrichment_pipeline.config import (
    CONNECTOR_SETTINGS,
    GLOBAL_PIPELINE,
    MYSQL_DBS,
    POSTGRES_DBS,
)
from etl_enrichment_pipeline.models import (
    CanonicalSchema,
    FinalOutput,
    PipelineState,
)
from etl_enrichment_pipeline.rules import RULES_DIR

__all__ = [
    "__version__",
    "CanonicalSchema",
    "PipelineState",
    "FinalOutput",
    "GLOBAL_PIPELINE",
    "CONNECTOR_SETTINGS",
    "POSTGRES_DBS",
    "MYSQL_DBS",
    "RULES_DIR",
]
