"""Per-agent output BaseModels.

Each agent in the pipeline produces a structured output that is stored
in the shared PipelineState. These types define the shape of those outputs.

Corresponds to master plan §Agent Responsibilities (agents 1-11).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from etl_enrichment_pipeline.models.canonical import CanonicalSchema


class ExtractionOutput(BaseModel):
    """Output from the schema extraction agent (agent 1).

    Wraps the canonical schema together with extraction metadata.
    """

    canonical_schema: CanonicalSchema | None = None
    tables_extracted: int = 0
    columns_extracted: int = 0


class DescriptionOutput(BaseModel):
    """Output from the description agent (agent 2).

    Natural-language descriptions for tables, columns, and views.
    """

    table_descriptions: dict[str, str] = Field(default_factory=dict)
    column_descriptions: dict[str, dict[str, str]] = Field(default_factory=dict)


class BusinessRoleOutput(BaseModel):
    """Output from the business role agent (agent 3).

    Classifies tables into roles such as master_data, transactional, reference, etc.
    """

    model_config = ConfigDict(extra="forbid")

    roles: dict[str, str] = Field(default_factory=dict)


class DomainOutput(BaseModel):
    """Output from the domain agent (agent 4).

    Detects the business domain of tables (Healthcare, Banking, Retail, etc.).
    """

    model_config = ConfigDict(extra="forbid")

    domains: dict[str, str] = Field(default_factory=dict)


class SemanticTypeOutput(BaseModel):
    """Output from the semantic type agent (agent 5).

    Detects business meaning of columns (EMAIL, PHONE, ADDRESS, etc.).
    """

    model_config = ConfigDict(extra="forbid")

    semantic_types: dict[str, str] = Field(default_factory=dict)


class EntityDiscoveryOutput(BaseModel):
    """Output from the entity discovery agent (agent 6).

    Converts schema objects into business entity names.
    """

    model_config = ConfigDict(extra="forbid")

    entities: list[str] = Field(default_factory=list)


class RelationshipIntelligenceOutput(BaseModel):
    """Output from the relationship intelligence agent (agent 7).

    Physical and entity-level relationships extracted from the schema.
    """

    physical_relationships: list[dict[str, str]] = Field(default_factory=list)
    entity_relationships: list[dict[str, str]] = Field(default_factory=list)


class UseCaseOutput(BaseModel):
    """Output from the use case agent (agent 8).

    Business use cases derived from the schema (Appointment Scheduling, etc.).
    """

    use_cases: list[dict[str, str]] = Field(default_factory=list)


class SampleQueryOutput(BaseModel):
    """Output from the sample query agent (agent 9).

    Sample business queries with natural-language question and SQL.
    """

    queries: list[dict[str, str]] = Field(default_factory=list)


class PatternDetectionOutput(BaseModel):
    """Output from the pattern detection agent (agent 10).

    Detected schema patterns (audit_trail, soft_delete, multi_tenancy, etc.).
    """

    patterns: list[dict[str, str]] = Field(default_factory=list)


class ValidationOutput(BaseModel):
    """Output from the validation agent (agent 11).

    Aggregated validation results with pass/fail status.
    """

    issues: list[dict[str, str]] = Field(default_factory=list)
    is_valid: bool = True


__all__ = [
    "BusinessRoleOutput",
    "DescriptionOutput",
    "DomainOutput",
    "EntityDiscoveryOutput",
    "ExtractionOutput",
    "PatternDetectionOutput",
    "RelationshipIntelligenceOutput",
    "SampleQueryOutput",
    "SemanticTypeOutput",
    "UseCaseOutput",
    "ValidationOutput",
]
