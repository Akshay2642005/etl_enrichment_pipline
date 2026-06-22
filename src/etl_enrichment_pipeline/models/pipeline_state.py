"""Shared LangGraph pipeline state.

Defines the PipelineState that is passed between LangGraph nodes,
along with simple type aliases used throughout the pipeline.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from etl_enrichment_pipeline.models.canonical import CanonicalSchema

# ---------------------------------------------------------------------------
# Type aliases — simple named aliases for readability across the pipeline.
# These replace ad-hoc TypedDict usage while keeping declarations compact.
# ---------------------------------------------------------------------------

DescriptionMap = dict[str, Any]
"""Maps table/column identifiers to their natural-language descriptions.
Stored as a nested dict with ``table_descriptions`` and
``column_descriptions`` keys."""

BusinessRoleMap = dict[str, str]
"""Maps table names to business role labels (e.g. 'master_data', 'transactional')."""

DomainResult = dict[str, str]
"""Maps table names to detected business domains (e.g. 'Healthcare', 'Banking')."""

SemanticTypeMap = dict[str, str]
"""Maps column identifiers to semantic type labels (e.g. 'EMAIL', 'PHONE')."""

EntityList = list[str]
"""Ordered list of discovered business entity names."""

RelationshipList = list[dict[str, str]]
"""List of entity-relationship descriptors
with keys such as 'entity' / 'related_entities'.

Note: the PipelineState stores entity_relationships as a dict with
``physical_relationships`` and ``entity_relationships`` keys, so the
field type is ``dict[str, Any]`` rather than this alias."""

UseCaseList = list[dict[str, str]]
"""List of business use-case descriptors."""

SampleQueryList = list[dict[str, str]]
"""List of sample business queries (each with 'question' / 'sql' keys)."""

PatternList = list[dict[str, Any]]
"""List of detected schema patterns (e.g. 'audit_trail', 'soft_delete').

Items may contain list-valued keys (e.g. ``evidence``)."""

ValidationReport = dict[str, Any]
"""Aggregated validation results with 'status', 'issues', and other metadata."""


class PipelineState(BaseModel):
    """Mutable state passed between LangGraph nodes during pipeline execution.

    Each field corresponds to a stage in the enrichment pipeline.
    """

    raw_input: str | None = None
    canonical_schema: CanonicalSchema | None = None
    descriptions: DescriptionMap | None = None
    business_roles: BusinessRoleMap | None = None
    domains: DomainResult | None = None
    semantic_types: SemanticTypeMap | None = None
    entities: EntityList | None = None
    entity_relationships: dict[str, Any] | None = None
    use_cases: UseCaseList | None = None
    sample_queries: SampleQueryList | None = None
    patterns: PatternList | None = None
    validation_report: ValidationReport | None = None
    final_output: dict | None = None


__all__ = [
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
]
