"""Unit tests for NL2SQLGenerator."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from etl_enrichment_pipeline.agents.nl2sql_generator import (
    GenerationResult,
    NL2SQLGenerator,
)
from etl_enrichment_pipeline.core.context_builder import SchemaContext


@pytest.fixture
def mock_chat_openai():
    with patch(
        "etl_enrichment_pipeline.agents.nl2sql_generator.get_llm"
    ) as mock_fn:
        instance = MagicMock()
        mock_fn.return_value = instance
        yield instance


@pytest.fixture
def generator(mock_chat_openai):
    return NL2SQLGenerator()


@pytest.fixture
def sample_context():
    return SchemaContext(
        tables=[
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
            }
        ],
        columns=[],
        relationships=[],
        join_paths=[],
        entity_relationships=[],
    )


class TestGenerate:
    def test_returns_generation_result(self, generator, sample_context, mock_chat_openai):
        structured = MagicMock()
        structured.invoke.return_value = GenerationResult(
            sql="SELECT * FROM employee;",
            confidence=0.95,
            explanation="Simple select",
        )
        mock_chat_openai.with_structured_output.return_value = structured

        result = generator.generate("show me all employees", sample_context)
        assert isinstance(result, GenerationResult)
        assert result.sql == "SELECT * FROM employee;"
        assert result.confidence == 0.95
        assert result.explanation == "Simple select"

    def test_context_is_formatted_in_prompt(self, generator, sample_context, mock_chat_openai):
        structured = MagicMock()
        structured.invoke.return_value = GenerationResult(
            sql="SELECT * FROM employee;",
            confidence=0.95,
        )
        mock_chat_openai.with_structured_output.return_value = structured

        generator.generate("show me employees", sample_context)
        call_args = structured.invoke.call_args[0][0]
        system_msg = call_args[0]
        user_msg = call_args[1]
        assert system_msg["role"] == "system"
        assert user_msg["role"] == "user"
        assert "employee" in user_msg["content"]
        assert "question" in user_msg["content"].lower()

    def test_context_used_in_result(self, generator, sample_context, mock_chat_openai):
        structured = MagicMock()
        structured.invoke.return_value = GenerationResult(
            sql="SELECT * FROM employee;",
            confidence=0.95,
        )
        mock_chat_openai.with_structured_output.return_value = structured

        result = generator.generate("show me employees", sample_context)
        assert result.context_used is not None
        assert result.context_used["table_count"] == 1
        assert "employee" in result.context_used["table_names"]

    def test_llm_returns_none_returns_graceful_error(
        self, generator, sample_context, mock_chat_openai
    ):
        structured = MagicMock()
        structured.invoke.return_value = None
        mock_chat_openai.with_structured_output.return_value = structured

        result = generator.generate("show me employees", sample_context)
        assert result.sql == ""
        assert result.confidence == 0.0
        assert result.explanation == "LLM returned no result"

    def test_llm_returns_empty_sql_returns_low_confidence(
        self, generator, sample_context, mock_chat_openai
    ):
        structured = MagicMock()
        structured.invoke.return_value = GenerationResult(
            sql="   ",
            confidence=0.95,
        )
        mock_chat_openai.with_structured_output.return_value = structured

        result = generator.generate("show me employees", sample_context)
        assert result.sql.strip() == ""
        assert result.confidence == 0.0

    def test_llm_failure_returns_graceful_error(
        self, generator, sample_context, mock_chat_openai
    ):
        structured = MagicMock()
        structured.invoke.side_effect = RuntimeError("LLM unavailable")
        mock_chat_openai.with_structured_output.return_value = structured

        result = generator.generate("show me employees", sample_context)
        assert result.sql == ""
        assert result.confidence == 0.0
        assert "error" in (result.explanation or "").lower()

    def test_empty_context_produces_reasonable_output(
        self, generator, mock_chat_openai
    ):
        structured = MagicMock()
        structured.invoke.return_value = GenerationResult(
            sql="",
            confidence=0.0,
            explanation="No context",
        )
        mock_chat_openai.with_structured_output.return_value = structured

        empty_ctx = SchemaContext()
        result = generator.generate("show me employees", empty_ctx)
        assert isinstance(result, GenerationResult)

    def test_calls_with_structured_output(self, generator, sample_context, mock_chat_openai):
        structured = MagicMock()
        structured.invoke.return_value = GenerationResult(sql="SELECT 1;")
        mock_chat_openai.with_structured_output.return_value = structured

        generator.generate("test", sample_context)
        mock_chat_openai.with_structured_output.assert_called_once_with(
            GenerationResult, method="function_calling"
        )
