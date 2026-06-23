"""Agent node functions and rule engine for the ETL enrichment pipeline.

Each agent module exposes a LangGraph-compatible node function that accepts
a PipelineState and returns a PipelineState with enriched fields populated.
"""

from __future__ import annotations

import typing

# ---------------------------------------------------------------------------
# Safe (non-circular) top-level imports
# ---------------------------------------------------------------------------
from etl_enrichment_pipeline.agents.ddl_parser import ddl_to_json
from etl_enrichment_pipeline.agents.rule_engine import RuleEngine

# ---------------------------------------------------------------------------
# Lazy imports — these agent modules eventually import back into
# ``etl_enrichment_pipeline.core`` which itself imports from *this* package,
# causing a circular import at module-load time.
# ---------------------------------------------------------------------------
_deferred: dict[str, typing.Any] = {}


def __getattr__(name: str) -> typing.Any:
    if name in _deferred:
        return _deferred[name]

    _import_map: dict[str, tuple[str, str]] = {
        "business_role_node": (
            "etl_enrichment_pipeline.agents.business_role_agent",
            "business_role_node",
        ),
        "description_node": (
            "etl_enrichment_pipeline.agents.description_agent",
            "description_node",
        ),
        "domain_node": (
            "etl_enrichment_pipeline.agents.domain_agent",
            "domain_node",
        ),
        "entity_discovery_node": (
            "etl_enrichment_pipeline.agents.entity_discovery_agent",
            "entity_discovery_node",
        ),
        "pattern_detection_node": (
            "etl_enrichment_pipeline.agents.pattern_detection_agent",
            "pattern_detection_node",
        ),
        "relationship_intelligence_node": (
            "etl_enrichment_pipeline.agents.relationship_intelligence_agent",
            "relationship_intelligence_node",
        ),
        "sample_query_node": (
            "etl_enrichment_pipeline.agents.sample_query_agent",
            "sample_query_node",
        ),
        "semantic_type_node": (
            "etl_enrichment_pipeline.agents.semantic_type_agent",
            "semantic_type_node",
        ),
        "use_case_node": (
            "etl_enrichment_pipeline.agents.use_case_agent",
            "use_case_node",
        ),
        "validation_node": (
            "etl_enrichment_pipeline.agents.validation_agent",
            "validation_node",
        ),
    }
    if name in _import_map:
        import importlib

        mod_path, attr_name = _import_map[name]
        mod = importlib.import_module(mod_path)
        val = getattr(mod, attr_name)
        _deferred[name] = val
        return val

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "business_role_node",
    "ddl_to_json",
    "description_node",
    "domain_node",
    "entity_discovery_node",
    "pattern_detection_node",
    "relationship_intelligence_node",
    "RuleEngine",
    "sample_query_node",
    "semantic_type_node",
    "use_case_node",
    "validation_node",
]
