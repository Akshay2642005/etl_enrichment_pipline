"""Final enrichment output model.

Matches the master plan §Final Output Structure.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FinalOutput(BaseModel):
    """Complete enriched schema output ready for serialisation / export.

    All eleven sections from the master plan final output structure
    are represented as top-level fields.
    """

    metadata: dict[str, Any] = Field(default_factory=dict)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    views: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, str]] = Field(default_factory=list)
    entities: list[dict[str, str]] = Field(default_factory=list)
    entity_relationships: list[dict[str, str]] = Field(default_factory=list)
    business_processes: list[dict[str, str]] = Field(default_factory=list)
    use_cases: list[dict[str, str]] = Field(default_factory=list)
    sample_queries: list[dict[str, str]] = Field(default_factory=list)
    schema_patterns: list[dict[str, str]] = Field(default_factory=list)
    validation_report: list[dict[str, str]] = Field(default_factory=list)


__all__ = ["FinalOutput"]
