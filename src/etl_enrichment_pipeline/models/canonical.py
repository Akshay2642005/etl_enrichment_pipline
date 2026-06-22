"""Canonical schema models (Pydantic v2).

Defines the intermediate canonical representation of extracted schema metadata
before enrichment agents layer on additional context.

Matches the master plan §Canonical Schema Model:
  database_info, tables, views, indexes, functions, procedures, triggers, relationships
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatabaseInfo(BaseModel):
    """Metadata about the source database."""

    name: str | None = None
    vendor: str | None = None
    version: str | None = None


class ColumnSchema(BaseModel):
    """A single column's metadata extracted from the source database."""

    table_name: str
    column_name: str
    data_type: str
    max_length: int | None = None
    is_nullable: bool = True
    is_primary_key: bool = False
    default_value: str | None = None


class TableSchema(BaseModel):
    """A single table's schema metadata."""

    table_name: str
    columns: list[ColumnSchema] = Field(default_factory=list)
    table_type: str = "TABLE"
    description: str | None = None


class ViewSchema(BaseModel):
    """A database view definition."""

    view_name: str
    definition: str
    columns: list[ColumnSchema] = Field(default_factory=list)


class IndexSchema(BaseModel):
    """An index defined on a table."""

    index_name: str
    table_name: str
    column_names: list[str] = Field(default_factory=list)
    is_unique: bool = False


class FunctionSchema(BaseModel):
    """A stored function or routine."""

    function_name: str
    definition: str
    return_type: str | None = None


class ProcedureSchema(BaseModel):
    """A stored procedure."""

    procedure_name: str
    definition: str


class TriggerSchema(BaseModel):
    """A trigger defined on a table."""

    trigger_name: str
    table_name: str
    definition: str
    timing: str = ""
    event: str = ""


class RelationshipSchema(BaseModel):
    """A foreign-key relationship between two tables."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    constraint_name: str | None = None


class CanonicalSchema(BaseModel):
    """Top-level canonical representation of the extracted database schema.

    Every source must first be transformed into this structure
    before enrichment agents can operate on it.
    """

    database_info: DatabaseInfo = Field(default_factory=DatabaseInfo)
    tables: list[TableSchema] = Field(default_factory=list)
    views: list[ViewSchema] = Field(default_factory=list)
    indexes: list[IndexSchema] = Field(default_factory=list)
    functions: list[FunctionSchema] = Field(default_factory=list)
    procedures: list[ProcedureSchema] = Field(default_factory=list)
    triggers: list[TriggerSchema] = Field(default_factory=list)
    relationships: list[RelationshipSchema] = Field(default_factory=list)


__all__ = [
    "CanonicalSchema",
    "ColumnSchema",
    "DatabaseInfo",
    "FunctionSchema",
    "IndexSchema",
    "ProcedureSchema",
    "RelationshipSchema",
    "TableSchema",
    "TriggerSchema",
    "ViewSchema",
]
