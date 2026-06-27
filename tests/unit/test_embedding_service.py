"""Unit tests for EmbeddingService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from etl_enrichment_pipeline.core.embedding_service import (
    EmbeddingService,
    SchemaEmbedding,
)


@pytest.fixture
def mock_model():
    with patch(
        "etl_enrichment_pipeline.core.embedding_service.SentenceTransformer"
    ) as mock_cls:
        instance = MagicMock()
        instance.encode.side_effect = lambda texts, **kw: np.array(
            [[0.1 + j * 0.1] * 384 for j in range(len(texts))]
        )
        mock_cls.return_value = instance
        yield instance


@pytest.fixture
def service(mock_model):
    return EmbeddingService(model_name="test-model")


@pytest.fixture
def sample_metadata_child_keys():
    """Same structure as sample_metadata but uses child/parent relationship keys."""
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
                        "column_name": "dept_id",
                        "data_type": "int",
                        "semantic_type": "ID",
                        "description": "Department FK",
                        "is_primary_key": False,
                        "is_nullable": True,
                    },
                ],
            },
            {
                "table_name": "department",
                "description": "Departments",
                "business_role": "master_data",
                "domain": "HR",
                "columns": [
                    {
                        "column_name": "id",
                        "data_type": "int",
                        "semantic_type": "ID",
                        "description": "Dept ID",
                        "is_primary_key": True,
                        "is_nullable": False,
                    }
                ],
            },
        ],
        "relationships": [
            {
                "name": "fk_employee_department",
                "description": "Links employee to their department",
                "child_table": "employee",
                "child_column": "dept_id",
                "parent_table": "department",
                "parent_column": "id",
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
def sample_metadata():
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
                    }
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


class TestGenerateEmbeddings:
    def test_single_text_returns_384_dim_vector(self, service, mock_model):
        result = service.generate_embeddings(["hello world"])
        assert len(result) == 1
        assert len(result[0]) == 384

    def test_multiple_texts_returns_correct_count(self, service, mock_model):
        mock_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384])
        result = service.generate_embeddings(["a", "b"])
        assert len(result) == 2

    def test_empty_list_returns_empty_list(self, service, mock_model):
        result = service.generate_embeddings([])
        assert result == []
        mock_model.encode.assert_not_called()

    def test_encodes_with_convert_to_tensor_false(self, service, mock_model):
        mock_model.encode.return_value = np.array([[0.1] * 384])
        service.generate_embeddings(["test"])
        mock_model.encode.assert_called_once_with(["test"], convert_to_tensor=False)


class TestEmbedSchemaObjects:
    def test_produces_correct_count(self, service, mock_model, sample_metadata):
        results = service.embed_schema_objects(sample_metadata)
        assert len(results) == 7

    def test_table_embeddings_have_correct_fields(self, service, mock_model, sample_metadata):
        results = service.embed_schema_objects(sample_metadata)
        table_embs = [r for r in results if r.object_type == "table"]
        assert len(table_embs) == 2
        assert table_embs[0].object_name == "employee"
        assert table_embs[0].object_key == "table:employee"
        assert table_embs[0].metadata["table_name"] == "employee"

    def test_column_embeddings_have_correct_fields(self, service, mock_model, sample_metadata):
        results = service.embed_schema_objects(sample_metadata)
        col_embs = [r for r in results if r.object_type == "column"]
        assert len(col_embs) == 3
        assert col_embs[0].object_name == "employee.employee_id"

    def test_relationship_embeddings(self, service, mock_model, sample_metadata):
        results = service.embed_schema_objects(sample_metadata)
        rel_embs = [r for r in results if r.object_type == "relationship"]
        assert len(rel_embs) == 2
        fk_keys = {r.object_key for r in rel_embs}
        assert "relationship:employee.department_id->departmentsss.department_id" in fk_keys
        assert "entity_relationship:Employee->Department" in fk_keys

    def test_relationship_embeddings_with_child_parent_keys(
        self, service, mock_model, sample_metadata_child_keys
    ):
        """embed_schema_objects normalises child/parent → from/to keys."""
        results = service.embed_schema_objects(sample_metadata_child_keys)
        rel_embs = [r for r in results if r.object_type == "relationship"]
        assert len(rel_embs) == 2
        fk_keys = {r.object_key for r in rel_embs}
        assert "relationship:employee.dept_id->department.id" in fk_keys, (
            f"Expected relationship:employee.dept_id->department.id, got {fk_keys}"
        )
        # Verify metadata was normalised to from/to keys
        fk_meta = {r.object_key: r.metadata for r in rel_embs if r.object_type == "relationship"}
        for meta in fk_meta.values():
            if meta.get("relationship_type") == "foreign_key":
                assert "from_table" in meta, f"from_table missing in {meta}"
                assert "to_table" in meta, f"to_table missing in {meta}"

    def test_empty_metadata_returns_empty_list(self, service, mock_model):
        mock_model.encode.return_value = np.array([])
        results = service.embed_schema_objects({})
        assert results == []

    def test_schema_embedding_dataclass(self):
        emb = SchemaEmbedding(
            object_type="table",
            object_name="employee",
            object_key="table:employee",
            text_content="Table: employee",
            embedding=[0.1] * 384,
            metadata={"table_name": "employee"},
        )
        assert emb.object_type == "table"
        assert len(emb.embedding) == 384
