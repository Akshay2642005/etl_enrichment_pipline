"""Data models for the ETL enrichment pipeline."""

from etl_enrichment_pipeline.models.canonical import (
    CanonicalSchema,
    ColumnSchema,
    DatabaseInfo,
    FunctionSchema,
    IndexSchema,
    ProcedureSchema,
    RelationshipSchema,
    TableSchema,
    TriggerSchema,
    ViewSchema,
)
from etl_enrichment_pipeline.models.connection_schema import (
    ConnectionCredentials,
    CREATE_SAVED_CONNECTIONS_TABLE_SQL,
    SavedConnection,
    SavedConnectionSummary,
)
from etl_enrichment_pipeline.models.final_output import FinalOutput
from etl_enrichment_pipeline.models.pipeline_state import (
    BusinessRoleMap,
    DescriptionMap,
    DomainResult,
    EntityList,
    PatternList,
    PipelineState,
    RelationshipList,
    SampleQueryList,
    SemanticTypeMap,
    UseCaseList,
    ValidationReport,
)

__all__ = [
    # canonical
    "CanonicalSchema",
    "ColumnSchema",
    "DatabaseInfo",
    "FunctionSchema",
    "IndexSchema",
    "ProcedureSchema",
    "RelationshipSchema",
    "TableSchema",
    "TriggerSchema",
    "ViewSchema",
    # connection_schema
    "ConnectionCredentials",
    "CREATE_SAVED_CONNECTIONS_TABLE_SQL",
    "SavedConnection",
    "SavedConnectionSummary",
    # pipeline_state
    "BusinessRoleMap",
    "DescriptionMap",
    "DomainResult",
    "EntityList",
    "PatternList",
    "PipelineState",
    "RelationshipList",
    "SampleQueryList",
    "SemanticTypeMap",
    "UseCaseList",
    "ValidationReport",
    # final_output
    "FinalOutput",
]
