"""Business role agent — classifies tables into business role categories."""

from __future__ import annotations

from etl_enrichment_pipeline.models.pipeline_state import PipelineState


def business_role_node(state: PipelineState) -> PipelineState:
    """Classify tables as master_data, transactional, reference, audit, staging,
    reporting, fact, dimension, or junction.

    TODO: Implement in Phase 2
    """
    raise NotImplementedError("business_role_node not yet implemented")
