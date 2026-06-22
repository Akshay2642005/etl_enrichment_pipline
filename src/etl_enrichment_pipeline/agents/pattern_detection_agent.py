"""Pattern detection agent — detects schema patterns: audit_trail, soft_delete,
multi_tenancy, versioning, state_machine, event_sourcing."""

from __future__ import annotations

import yaml

from etl_enrichment_pipeline.models.pipeline_state import PipelineState
from etl_enrichment_pipeline.rules import RULES_DIR


def pattern_detection_node(state: PipelineState) -> PipelineState:
    """Detect common schema patterns (audit_trail, soft_delete, multi_tenancy,
    versioning, state_machine, event_sourcing).

    Loads pattern rules from pattern_rules.yaml, scans all tables in
    ``state.canonical_schema`` for indicator columns, and records every
    detected pattern along with the evidence columns found.
    """
    if state.canonical_schema is None:
        state.patterns = []
        return state

    rules_path = RULES_DIR / "pattern_rules.yaml"
    with open(rules_path) as f:
        rules = yaml.safe_load(f)

    patterns_config: dict = rules.get("patterns", {})
    detected: list[dict[str, str | list[str]]] = []

    for table in state.canonical_schema.tables:
        for pattern_name, pattern_def in patterns_config.items():
            indicators_lower = {i.lower() for i in pattern_def.get("indicators", [])}
            evidence = [
                col.column_name
                for col in table.columns
                if col.column_name.lower() in indicators_lower
            ]
            if evidence:
                detected.append({
                    "pattern": pattern_name,
                    "table": table.table_name,
                    "evidence": evidence,
                    "description": pattern_def.get("description", ""),
                })

    state.patterns = detected
    return state
