"""Unit tests for SQLValidator."""
from __future__ import annotations

import pytest

from etl_enrichment_pipeline.core.sql_validator import SQLValidator, ValidationResult


@pytest.fixture
def metadata():
    return {
        "tables": [
            {
                "table_name": "employee",
                "columns": [
                    {"column_name": "employee_id"},
                    {"column_name": "employee_name"},
                    {"column_name": "department_id"},
                ],
            },
            {
                "table_name": "departmentsss",
                "columns": [
                    {"column_name": "department_id"},
                    {"column_name": "department_name"},
                ],
            },
        ]
    }


@pytest.fixture
def validator(metadata):
    return SQLValidator(metadata=metadata)


class TestValidateHappyPath:
    def test_valid_select_returns_is_valid_true(self, validator):
        result = validator.validate("SELECT * FROM employee")
        assert result.is_valid is True

    def test_valid_select_with_where(self, validator):
        result = validator.validate(
            "SELECT e.employee_name FROM employee e WHERE e.department_id = 1"
        )
        assert result.is_valid is True

    def test_valid_join(self, validator):
        result = validator.validate(
            "SELECT e.* FROM employee e JOIN departmentsss d "
            "ON e.department_id = d.department_id"
        )
        assert result.is_valid is True

    def test_parsed_structure(self, validator):
        result = validator.validate("SELECT employee_id, employee_name FROM employee")
        assert result.is_valid is True
        assert result.parsed is not None
        assert "tables" in result.parsed
        assert "columns" in result.parsed
        assert "statement_type" in result.parsed
        assert result.parsed["statement_type"] == "SELECT"


class TestValidateSyntaxErrors:
    def test_syntax_error_returns_invalid(self, validator):
        result = validator.validate("SELECTT * FROM employee")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_malformed_sql_returns_error(self, validator):
        result = validator.validate("SELECT * FORM employee")
        assert result.is_valid is False

    def test_incomplete_sql_returns_error(self, validator):
        result = validator.validate("SELECT WHERE")
        assert result.is_valid is False

    def test_confidence_is_zero_on_error(self, validator):
        result = validator.validate("SELECTT 1")
        assert result.confidence == 0.0


class TestValidateDangerousOperations:
    def test_drop_statement_is_caught(self, validator):
        result = validator.validate("DROP TABLE employee")
        assert any("DROP" in e for e in result.errors)

    def test_create_statement_is_caught(self, validator):
        result = validator.validate("CREATE TABLE test (id int)")
        assert any("CREATE" in e for e in result.errors)

    def test_alter_statement_is_caught(self, validator):
        result = validator.validate("ALTER TABLE employee ADD COLUMN test int")
        assert any("ALTER" in e for e in result.errors)

    def test_truncate_is_caught(self, validator):
        result = validator.validate("TRUNCATE TABLE employee")
        assert any("TRUNCATE" in e for e in result.errors)

    def test_delete_without_where_is_caught(self, validator):
        result = validator.validate("DELETE FROM employee")
        assert any("DELETE" in e for e in result.errors)

    def test_delete_with_where_is_allowed(self, validator):
        result = validator.validate(
            "DELETE FROM employee WHERE employee_id = 1"
        )
        assert result.is_valid is True
        assert not any("DELETE" in e for e in result.errors)

    def test_update_without_where_is_caught(self, validator):
        result = validator.validate("UPDATE employee SET employee_name = 'test'")
        assert any("UPDATE" in e for e in result.errors)

    def test_update_with_where_is_allowed(self, validator):
        result = validator.validate(
            "UPDATE employee SET employee_name = 'test' WHERE employee_id = 1"
        )
        assert result.is_valid is True
        assert not any("UPDATE" in e for e in result.errors)


class TestValidateEmptyInput:
    def test_empty_string_returns_invalid(self, validator):
        result = validator.validate("")
        assert result.is_valid is False
        assert any("Empty" in e for e in result.errors)

    def test_none_returns_invalid(self, validator):
        result = validator.validate(None)
        assert result.is_valid is False
        assert any("Empty" in e for e in result.errors)

    def test_whitespace_only_returns_invalid(self, validator):
        result = validator.validate("   ")
        assert result.is_valid is False
        assert any("Empty" in e for e in result.errors)

    def test_confidence_is_zero(self, validator):
        result = validator.validate("")
        assert result.confidence == 0.0


class TestValidateTableWarnings:
    def test_unknown_table_generates_warning(self, validator):
        result = validator.validate("SELECT * FROM nonexistent_table")
        assert result.is_valid is True
        assert any("nonexistent_table" in w for w in result.warnings)

    def test_unknown_column_generates_warning(self, validator):
        result = validator.validate(
            "SELECT employee.nonexistent_col FROM employee"
        )
        assert result.is_valid is True
        assert any("nonexistent_col" in w for w in result.warnings)

    def test_known_table_no_warning(self, validator):
        result = validator.validate("SELECT * FROM employee")
        warnings_about_tables = [
            w for w in result.warnings if "Table '" in w
        ]
        assert len(warnings_about_tables) == 0

    def test_confidence_reduced_for_warnings(self, validator):
        result = validator.validate("SELECT * FROM nonexistent_table")
        assert result.confidence < 1.0


class TestInitWithPath:
    def test_no_metadata_uses_empty_map(self, tmp_path):
        v = SQLValidator(metadata_path=str(tmp_path / "nonexistent.json"))
        assert len(v.table_names) == 0

    def test_no_args_uses_empty_map(self):
        v = SQLValidator()
        assert len(v.table_names) == 0


class TestValidationResult:
    def test_defaults(self):
        r = ValidationResult()
        assert r.is_valid is True
        assert r.errors == []
        assert r.warnings == []
        assert r.confidence == 1.0
