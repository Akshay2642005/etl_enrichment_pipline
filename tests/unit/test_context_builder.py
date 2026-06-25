"""Unit tests for ContextBuilder."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etl_enrichment_pipeline.core.context_builder import (
    ContextBuilder,
    SchemaContext,
    _table_to_entity_name,
)
from etl_enrichment_pipeline.core.embedding_service import (
    EmbeddingService,
    SchemaEmbedding,
)
from etl_enrichment_pipeline.core.graph_store import JoinPath
from etl_enrichment_pipeline.core.vector_store import SchemaEmbeddingResult


@pytest.fixture
def mock_embedding_service():
    svc = MagicMock(spec=EmbeddingService)
    svc.generate_embeddings.return_value = [[0.1] * 384]
    return svc


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    store.search_similar = AsyncMock(
        side_effect=lambda qe, object_type, top_k: {
            "table": [
                SchemaEmbeddingResult(
                    object_type="table",
                    object_name="employee",
                    object_key="table:employee",
                    text_content="Table: employee",
                    embedding=[0.1] * 384,
                    metadata={
                        "table_name": "employee",
                        "description": "Employee records",
                        "business_role": "master_data",
                    },
                    similarity=0.95,
                )
            ],
            "column": [
                SchemaEmbeddingResult(
                    object_type="column",
                    object_name="employee.employee_name",
                    object_key="column:employee.employee_name",
                    text_content="Column: employee.employee_name",
                    embedding=[0.1] * 384,
                    metadata={
                        "table_name": "employee",
                        "column_name": "employee_name",
                        "data_type": "varchar",
                        "semantic_type": "NAME",
                    },
                    similarity=0.90,
                )
            ],
            "relationship": [
                SchemaEmbeddingResult(
                    object_type="relationship",
                    object_name="employee.department_id->departmentsss"
                    ".department_id",
                    object_key="relationship:employee.department_id"
                    "->departmentsss.department_id",
                    text_content="FK: employee.department_id -> "
                    "departmentsss.department_id",
                    embedding=[0.1] * 384,
                    metadata={
                        "from_table": "employee",
                        "from_column": "department_id",
                        "to_table": "departmentsss",
                        "to_column": "department_id",
                        "relationship_type": "foreign_key",
                    },
                    similarity=0.85,
                )
            ],
        }[object_type]
    )
    return store


@pytest.fixture
def mock_graph_store():
    store = AsyncMock()
    store.find_join_paths = AsyncMock(
        return_value=[
            JoinPath(
                tables=["employee", "departmentsss"],
                path=[
                    (
                        "employee",
                        "department_id",
                        "departmentsss",
                        "department_id",
                    )
                ],
                hops=1,
            )
        ]
    )
    return store


@pytest.fixture
def enriched_metadata():
    return {
        "tables": [
            {
                "table_name": "employee",
                "description": "Employee records",
                "business_role": "master_data",
                "domain": "HR",
                "columns": [
                    {
                        "column_name": "employee_id",
                        "data_type": "int",
                        "semantic_type": "ID",
                        "description": "Unique ID",
                        "is_primary_key": True,
                        "is_nullable": False,
                    },
                    {
                        "column_name": "employee_name",
                        "data_type": "varchar",
                        "semantic_type": "NAME",
                        "description": "Full name",
                        "is_primary_key": False,
                        "is_nullable": True,
                    },
                    {
                        "column_name": "department_id",
                        "data_type": "int",
                        "semantic_type": "ID",
                        "description": "FK to department",
                        "is_primary_key": False,
                        "is_nullable": True,
                    },
                ],
            },
            {
                "table_name": "departmentsss",
                "description": "Departments",
                "business_role": "master_data",
                "domain": "HR",
                "columns": [
                    {
                        "column_name": "department_id",
                        "data_type": "int",
                        "semantic_type": "ID",
                        "description": "Dept ID",
                        "is_primary_key": True,
                        "is_nullable": False,
                    },
                    {
                        "column_name": "department_name",
                        "data_type": "varchar",
                        "semantic_type": "NAME",
                        "description": "Dept name",
                        "is_primary_key": False,
                        "is_nullable": True,
                    },
                ],
            },
        ],
        "relationships": [
            {
                "from_table": "employee",
                "from_column": "department_id",
                "to_table": "departmentsss",
                "to_column": "department_id",
            }
        ],
        "entity_relationships": [
            {
                "entity": "Employee",
                "related_entities": "Department",
                "business_meaning": "An employee belongs to one department",
            }
        ],
    }


@pytest.fixture
def builder(enriched_metadata, mock_embedding_service):
    return ContextBuilder(
        enriched_metadata=enriched_metadata,
        embedding_service=mock_embedding_service,
    )


class TestBuildContext:
    @pytest.mark.asyncio
    async def test_returns_schema_context_with_correct_fields(
        self, builder, mock_vector_store, mock_graph_store
    ):
        context = await builder.build_context(
            "show me employees",
            mock_vector_store,
            mock_graph_store,
        )
        assert isinstance(context, SchemaContext)
        assert len(context.tables) > 0
        assert len(context.columns) > 0
        assert len(context.relationships) > 0
        assert len(context.join_paths) > 0

    @pytest.mark.asyncio
    async def test_table_enriched_from_metadata(
        self, builder, mock_vector_store, mock_graph_store
    ):
        context = await builder.build_context(
            "show me employees",
            mock_vector_store,
            mock_graph_store,
        )
        tbl = context.tables[0]
        assert tbl["table_name"] == "employee"
        assert len(tbl.get("columns", [])) == 3

    @pytest.mark.asyncio
    async def test_join_paths_included(
        self, builder, mock_vector_store, mock_graph_store
    ):
        context = await builder.build_context(
            "show me employees",
            mock_vector_store,
            mock_graph_store,
        )
        assert len(context.join_paths) >= 1
        jp = context.join_paths[0]
        assert "employee" in jp["tables"]
        assert "hops" in jp

    @pytest.mark.asyncio
    async def test_no_duplicate_tables(
        self, builder, mock_vector_store, mock_graph_store
    ):
        context = await builder.build_context(
            "show me employees",
            mock_vector_store,
            mock_graph_store,
        )
        table_names = [t["table_name"] for t in context.tables]
        assert len(table_names) == len(set(table_names))


class TestBuildContextEmpty:
    @pytest.mark.asyncio
    async def test_empty_question_returns_context_with_defaults(self, builder):
        vs = AsyncMock()
        vs.search_similar = AsyncMock(return_value=[])
        gs = AsyncMock()
        gs.find_join_paths = AsyncMock(return_value=[])
        context = await builder.build_context("", vs, gs)
        assert isinstance(context, SchemaContext)
        assert context.tables == []
        assert context.columns == []


class TestFormatPrompt:
    def test_returns_string(self, builder):
        context = SchemaContext(
            tables=[
                {
                    "table_name": "employee",
                    "description": "Records",
                    "business_role": "master_data",
                    "domain": "HR",
                    "columns": [],
                }
            ]
        )
        prompt = builder.format_prompt(context)
        assert isinstance(prompt, str)
        assert "Employee" in prompt or "employee" in prompt
        assert "Tables" in prompt

    def test_empty_context_returns_empty_string(self, builder):
        context = SchemaContext()
        prompt = builder.format_prompt(context)
        assert prompt == ""

    def test_includes_relationships(self, builder):
        context = SchemaContext(
            relationships=[
                {
                    "from_table": "employee",
                    "from_column": "department_id",
                    "to_table": "departmentsss",
                    "to_column": "department_id",
                }
            ]
        )
        prompt = builder.format_prompt(context)
        assert "Foreign Key" in prompt
        assert "employee" in prompt


class TestTableToEntityName:
    def test_snake_case_to_pascal_case(self):
        assert _table_to_entity_name("employee") == "Employee"

    def test_multi_word(self):
        assert _table_to_entity_name("employee_role") == "Employee_Role"

    def test_already_pascal(self):
        assert _table_to_entity_name("Employee") == "Employee"


class TestFromJson:
    def test_from_json_with_valid_path(self, tmp_path, enriched_metadata):
        import json
        p = tmp_path / "test_metadata.json"
        p.write_text(json.dumps(enriched_metadata), encoding="utf-8")
        builder = ContextBuilder.from_json(json_path=str(p))
        assert builder._metadata is not None
        assert "tables" in builder._metadata
