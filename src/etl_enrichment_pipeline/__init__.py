"""ETL Enrichment Pipeline - Core package."""

__version__ = "0.1.0"

from config.config_global import (  # type: ignore
    CONNECTOR_SETTINGS,
    GLOBAL_PIPELINE,
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
    "RULES_DIR",
]
