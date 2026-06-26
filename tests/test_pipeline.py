"""Tests for the pipeline runner and JSON adapter functions.

Covers three input paths:
  - ``run_pipeline_from_raw_json``  (raw dict input)
  - ``run_pipeline_from_sql``       (SQL DDL file  → ddl_to_json → pipeline)
  - ``run_pipeline_from_db``        (live DB name  → extract_postgres_schema → pipeline)

Also covers the helper functions:
  - ``raw_json_to_canonical_schema``
  - ``load_raw_metadata``
  - ``run_pipeline``
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etl_enrichment_pipeline.core.pipeline import (
    load_raw_metadata,
    raw_json_to_canonical_schema,
    run_pipeline,
    run_pipeline_from_raw_json,
)
from etl_enrichment_pipeline.core.orchestrator import (
    run_pipeline_from_sql,
)
from etl_enrichment_pipeline.models.canonical import CanonicalSchema, ColumnSchema, RelationshipSchema, TableSchema, ViewSchema

# ============================================================================
# raw_json_to_canonical_schema
# ============================================================================


class TestRawJsonToCanonicalSchema:
    """Tests for the raw dict → CanonicalSchema adapter."""

    def test_minimal_conversion(self):
        """Convert a minimal raw metadata dict to CanonicalSchema correctly."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "attendance",
                    "columns": [
                        {"column_name": "id", "data_type": "integer", "nullable": False},
                        {"column_name": "name", "data_type": "varchar", "nullable": True},
                    ],
                    "constraints": [
                        {
                            "constraint_name": "attendance_pkey",
                            "constraint_type": "PRIMARY KEY",
                            "column_name": "id",
                        },
                    ],
                    "relationships": [
                        {
                            "child_column": "dept_id",
                            "parent_table": "department",
                            "parent_column": "id",
                        },
                    ],
                },
            ],
        }

        result = raw_json_to_canonical_schema(raw)

        # -- database_info --
        assert result.database_info.vendor == "postgresql"
        assert result.database_info.name == "public"

        # -- tables --
        assert len(result.tables) == 1
        table = result.tables[0]
        assert table.table_name == "attendance"
        assert table.table_type == "TABLE"

        # -- columns --
        assert len(table.columns) == 2

        col_id = table.columns[0]
        assert col_id.column_name == "id"
        assert col_id.data_type == "integer"
        assert col_id.table_name == "attendance"
        assert col_id.is_nullable is False  # nullable: false
        assert col_id.is_primary_key is True  # PRIMARY KEY constraint

        col_name = table.columns[1]
        assert col_name.column_name == "name"
        assert col_name.data_type == "varchar"
        assert col_name.is_nullable is True  # nullable: true (explicit)
        assert col_name.is_primary_key is False  # no PK constraint

        # -- relationships --
        assert len(result.relationships) == 1
        rel = result.relationships[0]
        assert rel.from_table == "attendance"
        assert rel.from_column == "dept_id"
        assert rel.to_table == "department"
        assert rel.to_column == "id"

        # -- views (not populated by current implementation) --
        assert result.views == []

    def test_nullable_defaults_to_true_when_missing(self):
        """When 'nullable' key is absent, is_nullable defaults to True."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "test",
                    "columns": [
                        {"column_name": "col_a", "data_type": "int"},
                        {"column_name": "col_b", "data_type": "text", "nullable": True},
                        {"column_name": "col_c", "data_type": "text", "nullable": None},
                    ],
                    "constraints": [],
                    "relationships": [],
                },
            ],
        }
        result = raw_json_to_canonical_schema(raw)
        assert len(result.tables) == 1
        cols = result.tables[0].columns
        # missing → True
        assert cols[0].is_nullable is True
        # explicit True → True
        assert cols[1].is_nullable is True
        # None → treated as truthy → True
        assert cols[2].is_nullable is True

    def test_nullable_false_mapped_correctly(self):
        """nullable: false maps to is_nullable=False."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "t",
                    "columns": [
                        {"column_name": "pk", "data_type": "int", "nullable": False},
                        {"column_name": "req", "data_type": "text", "nullable": False},
                    ],
                    "constraints": [],
                    "relationships": [],
                },
            ],
        }
        result = raw_json_to_canonical_schema(raw)
        for col in result.tables[0].columns:
            assert col.is_nullable is False

    def test_primary_key_from_constraints(self):
        """PRIMARY KEY constraint sets is_primary_key on the correct column."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "orders",
                    "columns": [
                        {"column_name": "order_id", "data_type": "int"},
                        {"column_name": "line_item", "data_type": "int"},
                        {"column_name": "name", "data_type": "text"},
                    ],
                    "constraints": [
                        {
                            "constraint_name": "orders_pkey",
                            "constraint_type": "PRIMARY KEY",
                            "column_name": "order_id",
                        },
                        {
                            "constraint_name": "orders_line_key",
                            "constraint_type": "PRIMARY KEY",
                            "column_name": "line_item",
                        },
                    ],
                    "relationships": [],
                },
            ],
        }
        result = raw_json_to_canonical_schema(raw)
        cols = result.tables[0].columns
        by_name = {c.column_name: c for c in cols}
        assert by_name["order_id"].is_primary_key is True
        assert by_name["line_item"].is_primary_key is True
        assert by_name["name"].is_primary_key is False

    def test_no_constraints_means_no_primary_keys(self):
        """Tables without constraints get no primary-key columns."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "log",
                    "columns": [
                        {"column_name": "id", "data_type": "int"},
                    ],
                    "constraints": [],
                    "relationships": [],
                },
            ],
        }
        result = raw_json_to_canonical_schema(raw)
        assert result.tables[0].columns[0].is_primary_key is False

    def test_views_from_raw_json(self):
        """Views provided in raw JSON are parsed into the canonical schema."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [],
            "views": [
                {
                    "view_name": "active_users",
                    "definition": "SELECT * FROM users WHERE active = 1",
                },
                {
                    "view_name": "order_summary",
                    "definition": "SELECT o.id, SUM(li.total) FROM orders o ...",
                },
            ],
        }
        result = raw_json_to_canonical_schema(raw)
        assert len(result.views) == 2
        assert result.views[0].view_name == "active_users"
        assert result.views[0].definition == "SELECT * FROM users WHERE active = 1"
        assert result.views[1].view_name == "order_summary"
        assert result.views[1].definition == "SELECT o.id, SUM(li.total) FROM orders o ..."

    def test_empty_json(self):
        """Passing an empty dict returns a valid CanonicalSchema with defaults."""
        result = raw_json_to_canonical_schema({})
        assert isinstance(result, CanonicalSchema)
        assert result.tables == []
        assert result.relationships == []
        assert result.views == []
        assert result.database_info.name is None
        assert result.database_info.vendor is None

    def test_missing_tables_key(self):
        """Missing 'tables' key is equivalent to an empty tables list."""
        raw = {"database_type": "mysql", "schema": "test"}
        result = raw_json_to_canonical_schema(raw)
        assert result.tables == []
        assert result.database_info.vendor == "mysql"
        assert result.database_info.name == "test"

    def test_missing_columns_in_table(self):
        """A table with a missing 'columns' key gets an empty column list."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "empty_table",
                    "constraints": [],
                    "relationships": [],
                },
            ],
        }
        result = raw_json_to_canonical_schema(raw)
        assert len(result.tables) == 1
        assert result.tables[0].columns == []
        assert result.tables[0].table_name == "empty_table"

    def test_missing_relationships_key(self):
        """A table without 'relationships' key gets no relationships."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "standalone",
                    "columns": [{"column_name": "id", "data_type": "int"}],
                    "constraints": [],
                },
            ],
        }
        result = raw_json_to_canonical_schema(raw)
        assert result.relationships == []

    def test_case_insensitive_constraint_type(self):
        """Constraint type matching is case-insensitive."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "t1",
                    "columns": [
                        {"column_name": "a", "data_type": "int"},
                        {"column_name": "b", "data_type": "int"},
                    ],
                    "constraints": [
                        {
                            "constraint_name": "pk_a",
                            "constraint_type": "primary key",
                            "column_name": "a",
                        },
                    ],
                    "relationships": [],
                },
            ],
        }
        result = raw_json_to_canonical_schema(raw)
        cols = result.tables[0].columns
        by_name = {c.column_name: c for c in cols}
        assert by_name["a"].is_primary_key is True
        assert by_name["b"].is_primary_key is False

    def test_multiple_tables(self):
        """Multiple tables are all converted and cross-table relationships preserved."""
        raw = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "customers",
                    "columns": [{"column_name": "id", "data_type": "int"}],
                    "constraints": [],
                    "relationships": [],
                },
                {
                    "table_name": "orders",
                    "columns": [{"column_name": "id", "data_type": "int"}],
                    "constraints": [],
                    "relationships": [
                        {
                            "child_column": "customer_id",
                            "parent_table": "customers",
                            "parent_column": "id",
                        },
                    ],
                },
            ],
        }
        result = raw_json_to_canonical_schema(raw)
        assert len(result.tables) == 2
        assert result.tables[0].table_name == "customers"
        assert result.tables[1].table_name == "orders"
        assert len(result.relationships) == 1
        assert result.relationships[0].from_table == "orders"
        assert result.relationships[0].to_table == "customers"


# ============================================================================
# load_raw_metadata
# ============================================================================


class TestLoadRawMetadata:
    """Tests for loading a raw_metadata.json file from disk."""

    def test_load_valid_json(self, tmp_path):
        """load_raw_metadata reads a JSON file and returns a CanonicalSchema."""
        raw = {
            "database_type": "postgresql",
            "schema": "inventory",
            "tables": [
                {
                    "table_name": "items",
                    "columns": [
                        {"column_name": "sku", "data_type": "varchar", "nullable": False},
                        {"column_name": "price", "data_type": "numeric"},
                    ],
                    "constraints": [
                        {
                            "constraint_name": "items_pkey",
                            "constraint_type": "PRIMARY KEY",
                            "column_name": "sku",
                        },
                    ],
                    "relationships": [],
                },
            ],
        }
        fp = tmp_path / "raw_metadata.json"
        fp.write_text(json.dumps(raw), encoding="utf-8")

        result = load_raw_metadata(str(fp))
        assert isinstance(result, CanonicalSchema)
        assert result.database_info.name == "inventory"
        assert len(result.tables) == 1
        assert result.tables[0].table_name == "items"
        assert result.tables[0].columns[0].is_primary_key is True

    def test_load_empty_json(self, tmp_path):
        """An empty JSON object ``{}`` produces a CanonicalSchema with defaults."""
        fp = tmp_path / "empty.json"
        fp.write_text("{}", encoding="utf-8")

        result = load_raw_metadata(str(fp))
        assert isinstance(result, CanonicalSchema)
        assert result.tables == []

    def test_load_nonexistent_file(self):
        """load_raw_metadata propagates FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            load_raw_metadata("/nonexistent/path/to/file.json")


# ============================================================================
# run_pipeline_from_raw_json
# ============================================================================


class TestRunPipelineFromRawJson:
    """Tests for ``run_pipeline_from_raw_json`` — the main dict-entry pipeline.

    We mock ``build_pipeline`` to avoid any LLM / LangGraph dependency.
    """

    @staticmethod
    def _make_mock_graph():
        """Return a minimal mock that replaces ``build_pipeline``."""

        class MockGraph:
            def invoke(self, state):
                """Return the same state — no LLM work."""
                return state

        return MockGraph

    def test_minimal_state_setup(self, monkeypatch):
        """Verify PipelineState is constructed correctly before graph invoke."""
        monkeypatch.setattr(
            "etl_enrichment_pipeline.core.pipeline.build_pipeline",
            self._make_mock_graph(),
        )

        raw_json = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "users",
                    "columns": [
                        {"column_name": "id", "data_type": "integer", "nullable": False},
                    ],
                    "constraints": [
                        {
                            "constraint_name": "users_pkey",
                            "constraint_type": "PRIMARY KEY",
                            "column_name": "id",
                        },
                    ],
                    "relationships": [],
                },
            ],
        }
        result = run_pipeline_from_raw_json(raw_json, source_label="test")

        # Verify the output metadata was correctly assembled from the schema
        assert result["metadata"]["database_type"] == "postgresql"
        assert result["metadata"]["database_name"] == "public"
        assert result["metadata"]["tables_count"] == 1
        assert result["metadata"]["columns_count"] == 1
        assert result["metadata"]["views_count"] == 0
        assert result["metadata"]["relationships_count"] == 0

        # Verify table and column data
        assert len(result["tables"]) == 1
        table = result["tables"][0]
        assert table["table_name"] == "users"
        assert len(table["columns"]) == 1
        col = table["columns"][0]
        assert col["column_name"] == "id"
        assert col["data_type"] == "integer"
        assert col["is_nullable"] is False
        assert col["is_primary_key"] is True

    def test_source_label_in_raw_input(self, monkeypatch):
        """The source_label is stored as raw_input in the initial PipelineState."""
        captured = []

        class MockGraph:
            def invoke(self, state):
                captured.append(state.raw_input)
                return state

        monkeypatch.setattr(
            "etl_enrichment_pipeline.core.pipeline.build_pipeline",
            lambda: MockGraph(),
        )

        raw_json = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [],
        }
        run_pipeline_from_raw_json(raw_json, source_label="my_source")
        assert captured == ["my_source"]

    def test_empty_raw_json(self, monkeypatch):
        """An empty raw dict produces valid output with zero tables."""
        monkeypatch.setattr(
            "etl_enrichment_pipeline.core.pipeline.build_pipeline",
            self._make_mock_graph(),
        )

        result = run_pipeline_from_raw_json({}, source_label="empty")
        assert result["metadata"]["tables_count"] == 0
        assert result["metadata"]["columns_count"] == 0
        assert result["tables"] == []


# ============================================================================
# run_pipeline_from_sql
# ============================================================================


class TestRunPipelineFromSql:
    """Tests for the SQL DDL → pipeline bridge."""

    def test_calls_ddl_to_json_and_pipeline(self, monkeypatch, tmp_path):
        """Verify ddl_to_json and run_pipeline_from_raw_json are called correctly."""
        sql_file = tmp_path / "test_schema.sql"
        sql_file.write_text("CREATE TABLE test (id INT);")

        output_dir = tmp_path / "output"

        ddl_result = {"database_type": "postgresql", "schema": "public", "tables": [], "views": []}
        pipeline_result = {"metadata": {}, "tables": [], "views": []}

        captured_ddl_args = []
        captured_pipeline_args = []

        def mock_ddl_to_json(filepath, database_type, schema, output_path):
            captured_ddl_args.append((filepath, database_type, schema, output_path))
            # Write the file so we can verify persistence
            Path(output_path).write_text(json.dumps(ddl_result), encoding="utf-8")
            return ddl_result

        def mock_run_pipeline_from_raw_json(raw_json, source_label):
            captured_pipeline_args.append((raw_json, source_label))
            return pipeline_result

        monkeypatch.setattr(
            "etl_enrichment_pipeline.core.orchestrator.ddl_to_json",
            mock_ddl_to_json,
        )
        monkeypatch.setattr(
            "etl_enrichment_pipeline.core.orchestrator.run_pipeline_from_raw_json",
            mock_run_pipeline_from_raw_json,
        )

        result = run_pipeline_from_sql(
            sql_file=str(sql_file),
            database_type="postgresql",
            schema="public",
            output_dir=str(output_dir),
        )

        # Final result is passed through from the pipeline mock
        assert result == pipeline_result

        # ddl_to_json called with correct arguments
        assert len(captured_ddl_args) == 1
        ddl_path, ddl_db_type, ddl_schema, ddl_out = captured_ddl_args[0]
        assert ddl_path == str(sql_file)
        assert ddl_db_type == "postgresql"
        assert ddl_schema == "public"
        assert "raw_from_ddl_test_schema.json" in ddl_out

        # Intermediate JSON file was persisted
        assert Path(ddl_out).exists()
        assert Path(ddl_out).read_text(encoding="utf-8") == json.dumps(ddl_result)

        # run_pipeline_from_raw_json called with correct args
        assert len(captured_pipeline_args) == 1
        assert captured_pipeline_args[0][0] == ddl_result
        assert captured_pipeline_args[0][1] == "ddl:test_schema"


# ============================================================================
# run_pipeline
# ============================================================================


class TestRunPipeline:
    """Tests for the convenience ``run_pipeline(input_path)`` function."""

    def test_delegates_to_run_pipeline_from_raw_json(self, monkeypatch, tmp_path):
        """run_pipeline reads a JSON file and delegates to run_pipeline_from_raw_json."""
        raw_json = {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "test_table",
                    "columns": [{"column_name": "id", "data_type": "int"}],
                    "constraints": [],
                    "relationships": [],
                },
            ],
        }
        fp = tmp_path / "input.json"
        fp.write_text(json.dumps(raw_json), encoding="utf-8")

        captured = []

        def mock_run(raw_json_, source_label):
            captured.append((raw_json_, source_label))
            return {"enriched": True}

        monkeypatch.setattr(
            "etl_enrichment_pipeline.core.pipeline.run_pipeline_from_raw_json",
            mock_run,
        )

        result = run_pipeline(str(fp))

        assert result == {"enriched": True}
        assert len(captured) == 1
        assert captured[0][0] == raw_json
        assert captured[0][1] == str(fp)
