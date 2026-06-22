"""Tests for Pydantic v2 data models."""


def test_canonical_schema_roundtrip(minimal_canonical_schema):
    """CanonicalSchema serializes and deserializes without data loss."""
    data = minimal_canonical_schema.model_dump()
    restored = type(minimal_canonical_schema).model_validate(data)
    assert restored == minimal_canonical_schema


def test_canonical_schema_defaults():
    """CanonicalSchema can be created with no arguments."""
    from etl_enrichment_pipeline.models.canonical import CanonicalSchema
    schema = CanonicalSchema()
    assert schema.tables == []
    assert schema.views == []
    assert schema.relationships == []


def test_pipeline_state_defaults(empty_pipeline_state):
    """PipelineState can be created with no arguments."""
    ps = empty_pipeline_state
    assert ps.raw_input is None
    assert ps.canonical_schema is None
    assert ps.final_output is None


def test_all_agent_stubs_importable():
    """All 11 agent node functions and RuleEngine are importable."""
    from etl_enrichment_pipeline.agents import (
        business_role_node,
        description_node,
        domain_node,
        entity_discovery_node,
        extraction_node,
        pattern_detection_node,
        relationship_intelligence_node,
        sample_query_node,
        semantic_type_node,
        use_case_node,
        validation_node,
    )
    from etl_enrichment_pipeline.agents.rule_engine import RuleEngine

    for name, node in [
        ("extraction_node", extraction_node),
        ("description_node", description_node),
        ("business_role_node", business_role_node),
        ("domain_node", domain_node),
        ("semantic_type_node", semantic_type_node),
        ("entity_discovery_node", entity_discovery_node),
        ("relationship_intelligence_node", relationship_intelligence_node),
        ("use_case_node", use_case_node),
        ("sample_query_node", sample_query_node),
        ("pattern_detection_node", pattern_detection_node),
        ("validation_node", validation_node),
    ]:
        assert callable(node), f"{name} is not callable"

    re = RuleEngine()
    assert re.rules_dir == ""
