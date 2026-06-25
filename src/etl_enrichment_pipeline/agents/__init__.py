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
        "consolidated_enrichment_node": (
            "etl_enrichment_pipeline.agents.consolidated_enrichment_agent",
            "consolidated_enrichment_node",
        ),
        "pattern_detection_node": (
            "etl_enrichment_pipeline.agents.pattern_detection_agent",
            "pattern_detection_node",
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
    "ddl_to_json",
    "RuleEngine",
]
