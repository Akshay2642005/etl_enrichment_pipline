"""Business role agent — classifies tables into business role categories."""

from __future__ import annotations
from typing import cast

from etl_enrichment_pipeline.models.agent_outputs import BusinessRoleOutput
from etl_enrichment_pipeline.models.pipeline_state import PipelineState


def business_role_node(state: PipelineState) -> PipelineState:
    """Classify tables as master_data, transactional, reference, audit, staging,
    reporting, fact, dimension, or junction.

    Uses a LangChain OpenAI agent (nvidia/nemotron-3-super-120b-a12b:free)
    with structured output to classify
    each table based on its name, column names/types, and FK relationships.
    Falls back gracefully if the LLM call fails (e.g. missing API key).
    """
    if state.canonical_schema is None:
        return state

    # Build FK lookup: for each table, list its FK relationships as readable strings
    fk_map: dict[str, list[str]] = {}
    for rel in state.canonical_schema.relationships:
        fk_map.setdefault(rel.from_table, []).append(
            f"{rel.from_table}.{rel.from_column} \u2192 {rel.to_table}.{rel.to_column}"
        )

    # Build per-table context: name, columns (with types and PK flag), FK relationships
    table_contexts: list[str] = []
    for table in state.canonical_schema.tables:
        col_info = ", ".join(
            f"{c.column_name} ({c.data_type}){' PK' if c.is_primary_key else ''}"
            for c in table.columns
        )
        fk_rels = fk_map.get(table.table_name, [])
        fk_str = "; ".join(fk_rels) if fk_rels else "None"
        table_contexts.append(
            f"Table: {table.table_name}\n"
            f"Columns: {col_info}\n"
            f"FK relationships: {fk_str}"
        )

    prompt = (
        "You are a database schema analyst. Classify each table into exactly one "
        "of these business roles:\n\n"
        "- master_data: Core business entities (employee, customer, product, "
        "department)\n"
        "- transactional: Records business events/transactions (attendance, "
        "order, payment)\n"
        "- reference: Lookup/reference data (status codes, types, categories)\n"
        "- audit: Audit trail/log tables\n"
        "- staging: Temporary data staging tables\n"
        "- reporting: Pre-aggregated reporting tables\n"
        "- fact: Fact tables in star schema\n"
        "- dimension: Dimension tables in star schema\n"
        "- junction: Many-to-many relationship tables "
        "(employee_role, student_course)\n\n"
        "Guidelines:\n"
        "- Tables with composite keys and FK references to 2+ tables \u2192 "
        "'junction'\n"
        "- Tables with only an ID and a name/description \u2192 'reference' or "
        "'master_data'\n"
        "- Tables with dates, amounts, or event timestamps \u2192 'transactional' "
        "or 'fact'\n"
        "- Tables with 'audit', 'log', 'history' in name \u2192 'audit'\n"
        "- Tables named 'staging', 'stage', 'temp' \u2192 'staging'\n"
        "- Tables with 'dim_' prefix or mostly descriptive columns \u2192 'dimension'\n"
        "- Tables with 'fact_' prefix \u2192 'fact'\n\n"
        "Return a map of table_name \u2192 role for each table listed below.\n\n"
        "Tables:\n" + "\n---\n".join(table_contexts)
    )

    try:
        from etl_enrichment_pipeline.core.llm import get_llm

        llm = get_llm()
        structured_llm = llm.with_structured_output(
            BusinessRoleOutput, method="function_calling"
        )
        result = cast("BusinessRoleOutput", structured_llm.invoke(prompt))
        state.business_roles = result.roles if result is not None else {}
    except Exception:
        # Graceful degradation — if API key is missing or any error occurs,
        # return state unchanged so the pipeline can continue without crashing
        pass

    return state
