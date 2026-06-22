"""YAML-driven rule-based classification engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RuleEngine(BaseModel):
    """YAML-driven rule-based classification engine.

    Loads rules from YAML files and applies them without LLM calls.
    Covers: PII detection, audit patterns, soft delete, common semantic types.

    TODO: Implement in Phase 2/3 — load from src/etl_enrichment_pipeline/rules/*.yaml
    """
    rules_dir: str = ""

    def classify(self, column_name: str, data_type: str) -> dict[str, Any]:
        raise NotImplementedError("RuleEngine.classify not yet implemented")
