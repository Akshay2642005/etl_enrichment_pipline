"""Domain agent — detects business domain (Healthcare, Banking, Retail, etc.)."""

from __future__ import annotations

from etl_enrichment_pipeline.models.pipeline_state import PipelineState


def domain_node(state: PipelineState) -> PipelineState:
    """Detect the business domain of each table (Healthcare, Banking, Retail, etc.).

    TODO: Implement in Phase 2
    """
    raise NotImplementedError("domain_node not yet implemented")
