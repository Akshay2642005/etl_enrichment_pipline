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

    metadata: dict[str, Any] = Field(default={})
    tables: list[dict[str, Any]] = Field(default=[])
    views: list[dict[str, Any]] = Field(default=[])
    relationships: list[dict[str, str]] = Field(default=[])
    entities: list[dict[str, str]] = Field(default=[])
    entity_relationships: list[dict[str, str]] = Field(default=[])
    business_processes: list[dict[str, str]] = Field(default=[])
    use_cases: list[dict[str, str]] = Field(default=[])
    sample_queries: list[dict[str, str]] = Field(default=[])
    schema_patterns: list[dict[str, str]] = Field(default=[])
    validation_report: list[dict[str, str]] = Field(default=[])


__all__ = ["FinalOutput"]
