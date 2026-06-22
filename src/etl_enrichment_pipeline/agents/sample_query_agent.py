"""Sample query agent — generates sample business queries
(Lookup, Reporting, Analytics, Aggregation, Relationship)."""

from __future__ import annotations

from etl_enrichment_pipeline.models.pipeline_state import PipelineState


def sample_query_node(state: PipelineState) -> PipelineState:
    """Generate sample business queries across categories: Lookup, Reporting,
    Analytics, Aggregation, Relationship.

    TODO: Implement in Phase 4
    """
    raise NotImplementedError("sample_query_node not yet implemented")
