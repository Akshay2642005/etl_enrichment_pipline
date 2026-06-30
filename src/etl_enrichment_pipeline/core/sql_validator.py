"""SQL validation against enriched metadata using sqlglot.

Validates PostgreSQL SQL syntax, table/column existence,
and detects dangerous operations (DROP, DELETE w/o WHERE, etc.).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import sqlglot
import sqlglot.expressions as exp


@dataclass
class ValidationResult:
    """Structured result of a SQL validation run."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parsed: dict[str, Any] | None = None
    confidence: float = 1.0


class SQLValidator:
    """Validates PostgreSQL SQL against an enriched metadata schema via sqlglot."""

    def __init__(self, metadata_path: str | Path | None = None, metadata: dict | None = None) -> None:
        self._table_map: dict[str, set[str]] = {}
        self._load_metadata(metadata_path, metadata)

    def _load_metadata(self, metadata_path: str | Path | None, metadata: dict | None) -> None:
        if metadata is not None:
            raw = metadata
        elif metadata_path is not None:
            path = Path(metadata_path)
            raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        else:
            raw = {}

        for table in raw.get("tables", []):
            name: str = table.get("table_name", "")
            cols: list[str] = [c.get("column_name", "") for c in table.get("columns", [])]
            self._table_map[name] = set(cols)

    @property
    def table_names(self) -> frozenset[str]:
        return frozenset(self._table_map)

    def validate(self, sql: str | None) -> ValidationResult:
        """Parse and validate a single SQL statement."""
        if not sql or not sql.strip():
            return ValidationResult(
                is_valid=False,
                errors=["Empty or None SQL statement"],
                confidence=0.0,
            )

        errors: list[str] = []
        warnings: list[str] = []
        dangerous: list[str] = []
        validation_errors: list[str] = []

        parsed = self._parse_sql(sql, errors)
        if parsed is None:
            return ValidationResult(is_valid=False, errors=errors, confidence=0.0)

        self._check_dialect(sql, warnings)

        tree = parsed[0] if isinstance(parsed, list) else parsed

        tables = list(tree.find_all(exp.Table))
        columns = list(tree.find_all(exp.Column))

        self._check_dangerous_operations(tree, dangerous)
        self._check_table_existence(tables, validation_errors)
        self._check_column_existence(columns, validation_errors)

        errors.extend(validation_errors)

        confidence = self._compute_confidence(errors, dangerous, validation_errors, warnings)

        return ValidationResult(
            is_valid=not errors,
            errors=errors + dangerous,
            warnings=warnings,
            parsed=self._build_parsed(tree) if not errors else None,
            confidence=confidence,
        )

    def _compute_confidence(
        self,
        errors: list[str],
        dangerous: list[str],
        validation_errors: list[str],
        all_warnings: list[str],
    ) -> float:
        if errors or validation_errors:
            return 0.0
        if dangerous:
            return 0.5
        if all_warnings:
            return 0.8
        return 1.0

    def _parse_sql(self, sql: str, errors: list[str]) -> list | None:
        try:
            parsed = sqlglot.parse(sql, dialect="postgres")
            if parsed is None or any(p is None for p in parsed):
                errors.append("Failed to parse SQL: parser returned None")
                return None
            return parsed
        except sqlglot.errors.ParseError as exc:
            errors.append(f"SQL syntax error: {exc}")
            return None
        except Exception as exc:
            errors.append(f"Unexpected parse error: {exc}")
            return None

    def _check_dialect(self, sql: str, warnings: list[str]) -> None:
        try:
            transpiled = sqlglot.transpile(sql, write="postgres")
            if transpiled and transpiled[0].strip().upper() != sql.strip().upper():
                warnings.append("SQL was normalised by dialect transpiler")
        except Exception:
            warnings.append("Dialect transpilation check failed")

    def _check_dangerous_operations(self, tree: exp.Expression, dangerous: list[str]) -> None:
        for _ in tree.find_all(exp.Drop):
            dangerous.append("Dangerous DDL statement detected: DROP")
        for _ in tree.find_all(exp.Create):
            dangerous.append("Dangerous DDL statement detected: CREATE")
        for _ in tree.find_all(exp.Alter):
            dangerous.append("Dangerous DDL statement detected: ALTER")
        for _ in tree.find_all(exp.TruncateTable):
            dangerous.append("Dangerous DDL statement detected: TRUNCATE")

        for node in tree.find_all(exp.Delete):
            if not node.find(exp.Where):
                dangerous.append("DELETE without WHERE clause — unsafe operation")
        for node in tree.find_all(exp.Update):
            if not node.find(exp.Where):
                dangerous.append("UPDATE without WHERE clause — unsafe operation")

    def _check_table_existence(self, tables: list[exp.Table], warnings: list[str]) -> None:
        for tbl in tables:
            tbl_name = tbl.name
            if tbl_name and tbl_name not in self._table_map:
                warnings.append(f"Table '{tbl_name}' not found in enriched metadata")

    def _check_column_existence(self, columns: list[exp.Column], warnings: list[str]) -> None:
        for col in columns:
            table_part = col.table
            col_name = col.name
            if table_part and table_part in self._table_map and col_name and col_name not in self._table_map[table_part]:
                warnings.append(f"Column '{col_name}' not found in table '{table_part}'")

    def _build_parsed(self, tree: exp.Expression) -> dict[str, Any]:
        tables = sorted({tbl.name for tbl in tree.find_all(exp.Table) if tbl.name})
        columns = sorted({col.name for col in tree.find_all(exp.Column) if col.name})
        return {
            "statement_type": tree.key.upper() if hasattr(tree, "key") else type(tree).__name__,
            "tables": tables,
            "columns": columns,
        }


__all__ = [
    "SQLValidator",
    "ValidationResult",
]
