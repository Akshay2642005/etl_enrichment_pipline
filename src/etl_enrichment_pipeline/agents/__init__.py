"""Agent node functions and rule engine for the ETL enrichment pipeline.

Each agent module exposes a LangGraph-compatible node function that accepts
a PipelineState and returns a PipelineState with enriched fields populated.
"""

from __future__ import annotations

from etl_enrichment_pipeline.agents.business_role_agent import business_role_node
from etl_enrichment_pipeline.agents.description_agent import description_node
from etl_enrichment_pipeline.agents.domain_agent import domain_node
from etl_enrichment_pipeline.agents.entity_discovery_agent import entity_discovery_node
from etl_enrichment_pipeline.agents.pattern_detection_agent import (
    pattern_detection_node,
)
from etl_enrichment_pipeline.agents.relationship_intelligence_agent import (
    relationship_intelligence_node,
)
from etl_enrichment_pipeline.agents.rule_engine import RuleEngine
from etl_enrichment_pipeline.agents.sample_query_agent import sample_query_node
from etl_enrichment_pipeline.agents.semantic_type_agent import semantic_type_node
from etl_enrichment_pipeline.agents.use_case_agent import use_case_node
from etl_enrichment_pipeline.agents.validation_agent import validation_node

__all__ = [
    "business_role_node",
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
