"""Use case agent — generates business use cases from the enriched schema."""

from __future__ import annotations

from etl_enrichment_pipeline.models.pipeline_state import PipelineState


def use_case_node(state: PipelineState) -> PipelineState:
    """Generate business use cases derived from the enriched schema.

    TODO: Implement in Phase 4
    """
    raise NotImplementedError("use_case_node not yet implemented")
