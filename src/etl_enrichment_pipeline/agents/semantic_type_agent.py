"""Semantic type agent — detects business meaning of columns
(EMAIL, PHONE, PII, etc.)."""

from __future__ import annotations

from etl_enrichment_pipeline.models.pipeline_state import PipelineState


def semantic_type_node(state: PipelineState) -> PipelineState:
    """Detect business meaning / semantic type of columns (EMAIL, PHONE, PII, etc.).

    TODO: Implement in Phase 3
    """
    raise NotImplementedError("semantic_type_node not yet implemented")
