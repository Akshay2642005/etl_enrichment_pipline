"""Database connection persistence models.

Defines the Pydantic models and SQL schema for saving database
connections along with their enriched metadata and insights.

Relationships:
    saved_connections
        ├── enriched_schema  (FinalOutput / CanonicalSchema as JSONB)
        └── insights         (InsightsResponse as JSONB)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConnectionCredentials(BaseModel):
    """Database connection credentials (sensitive — stored as JSONB)."""

    host: str = Field(default="localhost", description="Database host")
    port: int | str | None = Field(default=None, description="Database port")
    database: str = Field(..., description="Database name")
    username: str | None = Field(default=None, description="Database username")
    password: str | None = Field(default=None, description="Database password")


class SavedConnection(BaseModel):
    """A persisted database connection with its enriched schema + insights.

    This is the row-level model for the ``saved_connections`` table.
    """

    id: str | None = Field(default=None, description="UUID (server-generated)")
    name: str = Field(..., description="Human-readable connection name")
    description: str | None = Field(default=None, description="Optional description")
    database_type: str = Field(
        ...,
        description="Database type: postgres, mysql, mariadb, sqlserver, oracle, sqlite",
    )
    credentials: ConnectionCredentials = Field(
        ..., description="Connection credentials"
    )
    enriched_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="Full enriched metadata output from the pipeline",
    )
    insights: dict[str, Any] = Field(
        default_factory=dict,
        description="Generated insights (KPIs, insights, opportunities, art_of_the_possible)",
    )
    insights_hash: str | None = Field(
        default=None,
        description="SHA-256 hex digest of the insights payload (used to skip no-op writes)",
    )
    status: str = Field(
        default="active",
        description="Connection status: active, error, archived",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if enrichment/insights failed",
    )
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


class SavedConnectionSummary(BaseModel):
    """Lightweight view of a saved connection (no credentials or large payloads)."""

    id: str = Field(..., description="UUID")
    name: str = Field(..., description="Human-readable connection name")
    description: str | None = Field(default=None)
    database_type: str = Field(..., description="Database vendor")
    status: str = Field(default="active")
    table_count: int = Field(default=0, description="Number of tables in schema")
    view_count: int = Field(default=0, description="Number of views in schema")
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


# ---------------------------------------------------------------------------
# SQL schema — DDL for the saved_connections table
# ---------------------------------------------------------------------------

CREATE_SAVED_CONNECTIONS_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS saved_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT,
    database_type   TEXT NOT NULL,
    credentials     JSONB NOT NULL DEFAULT '{}',
    enriched_schema JSONB NOT NULL DEFAULT '{}',
    insights        JSONB NOT NULL DEFAULT '{}',
    insights_hash   VARCHAR(64),
    status          TEXT NOT NULL DEFAULT 'active',
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_saved_connections_status
    ON saved_connections (status);

CREATE INDEX IF NOT EXISTS idx_saved_connections_database_type
    ON saved_connections (database_type);

CREATE INDEX IF NOT EXISTS idx_saved_connections_created_at
    ON saved_connections (created_at DESC);
"""


MIGRATE_ADD_INSIGHTS_HASH_SQL = """
ALTER TABLE saved_connections
    ADD COLUMN IF NOT EXISTS insights_hash VARCHAR(64);
"""


__all__ = [
    "CREATE_SAVED_CONNECTIONS_TABLE_SQL",
    "MIGRATE_ADD_INSIGHTS_HASH_SQL",
    "ConnectionCredentials",
    "SavedConnection",
    "SavedConnectionSummary",
]
