"""Entity discovery agent — converts schema objects into business entities."""

from __future__ import annotations

from etl_enrichment_pipeline.models.pipeline_state import PipelineState


def entity_discovery_node(state: PipelineState) -> PipelineState:
    """Convert schema tables / views into business entities with attributes.

    TODO: Implement in Phase 3
    """
    raise NotImplementedError("entity_discovery_node not yet implemented")
