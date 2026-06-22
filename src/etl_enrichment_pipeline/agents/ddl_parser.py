"""DDL parser — converts raw SQL DDL statements to structured JSON.

Parses ``.sql`` files containing ``CREATE TABLE`` statements and produces
a JSON representation matching the ``raw_metadata.json`` structure.

Uses ``sqlglot`` as the primary parser (per the master plan).

Public API
----------
- ``ddl_to_json(filepath, database_type, schema)``
    Standalone function. Reads a ``.sql`` file, parses all ``CREATE TABLE``
    statements, and returns a dict in ``raw_metadata.json`` format.
"""

from __future__ import annotations

import json

import sqlglot
from sqlglot import exp


def ddl_to_json(
    filepath: str,
    database_type: str = "postgresql",
    schema: str = "public",
    output_path: str | None = None,
) -> dict:
    """Parse a SQL DDL file and return structured JSON metadata.

    Parameters
    ----------
    filepath :
        Path to the ``.sql`` file containing ``CREATE TABLE`` statements.
    database_type :
        Database vendor identifier (e.g. ``"postgresql"``, ``"mysql"``).
        Used to select the sqlglot dialect.
    schema :
        Database schema name (e.g. ``"public"``, ``"dbo"``).
    output_path :
        Optional path to write the JSON output to. If ``None``, the result
        is only returned (not persisted).

    Returns
    -------
    dict
        A dictionary with the structure::

            {
                "database_type": "postgresql",
                "schema": "public",
                "tables": [
                    {
                        "table_name": "attendance",
                        "columns": [
                            {"column_name": ..., "data_type": ..., "nullable": ...},
                            ...
                        ],
                        "constraints": [
                            {
                                "constraint_name": ...,
                                "constraint_type": ...,
                                "column_name": ...,
                            },
                            ...
                        ],
                        "relationships": [
                            {
                                "child_column": ...,
                                "parent_table": ...,
                                "parent_column": ...,
                            },
                            ...
                        ]
                    }
                ]
            }
    """
    with open(filepath, encoding="utf-8") as f:
        sql_text = f.read()

    dialect = _resolve_dialect(database_type)
    statements = sqlglot.parse(sql_text, dialect=dialect)

    tables: list[dict] = []

    for statement in statements:
        if statement is None:
            continue
        if isinstance(statement, exp.Create) and isinstance(statement.this, exp.Schema):
            parsed = _parse_create_table(statement)
            if parsed is not None:
                tables.append(parsed)

    result = {
        "database_type": database_type,
        "schema": schema,
        "tables": tables,
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_dialect(database_type: str) -> str:
    """Map a high-level database type to a sqlglot dialect name."""
    mapping = {
        "postgresql": "postgres",
        "mysql": "mysql",
        "mariadb": "mysql",
        "mssql": "tsql",
        "sqlite": "sqlite",
        "oracle": "oracle",
    }
    return mapping.get(database_type, database_type)


def _parse_create_table(create_stmt: exp.Create) -> dict | None:
    """Extract table metadata from a single ``CREATE TABLE`` AST node."""
    schema = create_stmt.this
    table_node = schema.this
    table_name = table_node.name if table_node else ""
    if not table_name:
        return None

    columns: list[dict] = []
    constraints: list[dict] = []
    relationships: list[dict] = []

    for expr in schema.expressions:
        if isinstance(expr, exp.ColumnDef):
            col = _parse_column_def(expr)
            columns.append(col)
        elif isinstance(expr, exp.Constraint):
            _parse_named_constraint(expr, table_name, constraints, relationships)
        else:
            _parse_bare_constraint(expr, table_name, constraints, relationships)

    return {
        "table_name": table_name,
        "columns": columns,
        "constraints": constraints,
        "relationships": relationships,
    }


def _parse_column_def(col: exp.ColumnDef) -> dict:
    """Extract column metadata from a ``ColumnDef`` AST node."""
    data_type = col.kind.sql() if col.kind else "unknown"

    nullable = True
    for cc in col.constraints:
        if isinstance(cc, exp.ColumnConstraint) and isinstance(
            cc.kind, exp.NotNullColumnConstraint
        ):
            nullable = False

    return {
        "column_name": col.name,
        "data_type": data_type.lower(),
        "nullable": nullable,
    }


def _get_parent_table(ref: exp.Reference) -> str:
    """Extract the referenced parent table name from a FOREIGN KEY reference."""
    if isinstance(ref.this, exp.Schema) and ref.this.this:
        return ref.this.this.name
    return ""


def _parse_named_constraint(
    expr: exp.Constraint,
    table_name: str,
    constraints: list[dict],
    relationships: list[dict],
) -> None:
    """Parse a named table-level constraint (``CONSTRAINT xxx ...``)."""
    constraint_name = expr.name

    for inner in expr.expressions:
        if isinstance(inner, exp.PrimaryKey):
            for pk_col in inner.expressions:
                constraints.append({
                    "constraint_name": constraint_name,
                    "constraint_type": "PRIMARY KEY",
                    "column_name": pk_col.name,
                })
        elif isinstance(inner, exp.ForeignKey):
            child_columns = [c.name for c in inner.expressions]
            ref = inner.args.get("reference")
            if ref is not None and isinstance(ref.this, exp.Schema):
                parent_table = _get_parent_table(ref)
                parent_columns = [c.name for c in ref.this.expressions]
                for child_col, parent_col in zip(
                    child_columns, parent_columns, strict=True
                ):
                    constraints.append({
                        "constraint_name": constraint_name,
                        "constraint_type": "FOREIGN KEY",
                        "column_name": child_col,
                    })
                    relationships.append({
                        "child_column": child_col,
                        "parent_table": parent_table,
                        "parent_column": parent_col,
                    })
        elif isinstance(inner, exp.Unique):
            for uq_col in inner.expressions:
                constraints.append({
                    "constraint_name": constraint_name,
                    "constraint_type": "UNIQUE",
                    "column_name": uq_col.name,
                })


def _parse_bare_constraint(
    expr: exp.Expression,
    table_name: str,
    constraints: list[dict],
    relationships: list[dict],
) -> None:
    """Parse an unnamed table-level constraint (e.g. bare ``PRIMARY KEY (col)``)."""
    if isinstance(expr, exp.PrimaryKey):
        for pk_col in expr.expressions:
            constraints.append({
                "constraint_name": f"{table_name}_pkey",
                "constraint_type": "PRIMARY KEY",
                "column_name": pk_col.name,
            })
    elif isinstance(expr, exp.ForeignKey):
        child_columns = [c.name for c in expr.expressions]
        ref = expr.args.get("reference")
        if ref is not None and isinstance(ref.this, exp.Schema):
            parent_table = _get_parent_table(ref)
            parent_columns = [c.name for c in ref.this.expressions]
            for child_col, parent_col in zip(
                child_columns, parent_columns, strict=True
            ):
                fk_name = f"{table_name}_{child_col}_fkey"
                constraints.append({
                    "constraint_name": fk_name,
                    "constraint_type": "FOREIGN KEY",
                    "column_name": child_col,
                })
                relationships.append({
                    "child_column": child_col,
                    "parent_table": parent_table,
                    "parent_column": parent_col,
                })
    elif isinstance(expr, exp.Unique):
        for uq_col in expr.expressions:
            constraints.append({
                "constraint_name": f"{table_name}_{uq_col.name}_key",
                "constraint_type": "UNIQUE",
                "column_name": uq_col.name,
            })


__all__ = ["ddl_to_json"]
