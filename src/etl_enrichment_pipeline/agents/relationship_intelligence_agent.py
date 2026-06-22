"""Relationship intelligence agent — infers physical and entity
relationships with business meaning."""

from __future__ import annotations

import logging
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from etl_enrichment_pipeline.core.llm import get_llm
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured-output schema for the LLM
# ---------------------------------------------------------------------------


class EntityRelationshipItem(BaseModel):
    """A single entity-level relationship inferred from FK constraints."""

    model_config = ConfigDict(extra="ignore")

    entity: str = Field(default="", description="Source business entity name (PascalCase)")
    related_entities: str = Field(
        default="", description="Comma-separated list of related entity names"
    )
    business_meaning: str = Field(
        default="",
        description="Natural-language description of the relationship "
        "including cardinality (e.g. 'An employee belongs to one department')",
    )


class EntityRelationships(BaseModel):
    """Container returned by the LLM."""

    model_config = ConfigDict(extra="ignore")

    entity_relationships: list[EntityRelationshipItem] = Field(
        default_factory=list,
        description="Entity-level relationships with business meaning",
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_RELATIONSHIP_SYSTEM_PROMPT = """\
You are a database schema analyst specializing in entity-relationship inference.
Given a list of business entities and the physical foreign-key (FK) relationships
between their underlying tables, infer the **entity-level relationships** and
describe their **business meaning**.

## Rules

1. **Map each FK to entity pairs**.
   For example:
   - FK: `employee.department_id \u2192 department.department_id`
     + entities: `Employee`, `Department`
     \u2192 Entity relationship: Employee \u2192 Department
       Business meaning: "An employee belongs to one department"

2. **Group related relationships** under the same source entity when possible.
   For example, if `Employee` has FKs to both `Department` and `Role`, produce
   one entry with multiple related entities rather than two separate entries.

3. **Describe cardinality naturally** in the business meaning (one-to-many,
   many-to-one, many-to-many).

4. **Only infer relationships** that are directly supported by the provided FK
   constraints and entity list. Do not invent relationships.

## Output

For each source entity that participates in at least one FK relationship,
produce one entry containing:
- **entity**: The source business entity name (PascalCase)
- **related_entities**: Comma-separated list of related PascalCase entity names
- **business_meaning**: A concise, natural-language description of how the
  entities relate to each other"""

_RELATIONSHIP_USER_PROMPT = """\
Analyse the following business entities and foreign-key relationships to infer
entity-level relationships with business meaning.

Discovered entities:
{entities}

Foreign-key relationships:
{physical_relationships}

For each source entity that participates in FK relationships, produce the
corresponding entity-level relationship entries with business meaning labels."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_entities(entities: list[str]) -> str:
    """Format the entity list for the LLM prompt."""
    if not entities:
        return "(no entities)"
    return "\n".join(f"  - {e}" for e in entities)


def _format_physical_relationships(
    physical: list[dict[str, str]],
) -> str:
    """Format physical FK relationships for the LLM prompt."""
    if not physical:
        return "(no relationships)"
    lines: list[str] = []
    for rel in physical:
        lines.append(
            f"  - {rel['from_table']}.{rel['from_column']} \u2192 "
            f"{rel['to_table']}.{rel['to_column']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


def relationship_intelligence_node(state: PipelineState) -> PipelineState:
    """Infer physical FK and entity-level relationships with business meaning labels.

    Extracts physical foreign-key relationships directly from the canonical
    schema (no LLM needed). If business entities are available, uses a
    LangChain ``ChatOpenRouter`` agent with structured output to map FK
    constraints into entity-level relationships with natural-language
    business meaning descriptions.

    Gracefully degrades (``state.entity_relationships`` set to an empty
    structure + warning log) when:

    - ``state.canonical_schema`` is ``None``
    - The ``OPENROUTER_API_KEY`` environment variable is not set
    - The LLM call fails for any other reason

    Args:
        state: The current pipeline state containing the canonical schema
            and optionally discovered entities.

    Returns:
        Updated pipeline state with ``entity_relationships`` populated.
    """
    # --- Early exit when there is no schema to analyse -----------------------
    if state.canonical_schema is None:
        logger.warning("canonical_schema is None — skipping relationship intelligence")
        return state

    # --- Physical relationships: extract from FK constraints (no LLM) --------
    physical: list[dict[str, str]] = []
    for rel in state.canonical_schema.relationships:
        physical.append(
            {
                "from_table": rel.from_table,
                "to_table": rel.to_table,
                "from_column": rel.from_column,
                "to_column": rel.to_column,
            }
        )

    logger.debug("Extracted %d physical FK relationship(s)", len(physical))

    # --- Entity relationships: use LLM if entities are available -------------
    entity_rels: list[dict[str, str]] = []
    if state.entities and physical:
        try:
            entities_str = _format_entities(state.entities)
            physical_str = _format_physical_relationships(physical)

            llm = get_llm()
            structured_llm = llm.with_structured_output(
                EntityRelationships, method="function_calling"
            )

            system_prompt = _RELATIONSHIP_SYSTEM_PROMPT
            user_prompt = _RELATIONSHIP_USER_PROMPT.format(
                entities=entities_str,
                physical_relationships=physical_str,
            )

            result = cast(
                "EntityRelationships",
                structured_llm.invoke(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ]
                ),
            )

            if result is not None:
                entity_rels = [
                    {
                        "entity": item.entity,
                        "related_entities": item.related_entities,
                        "business_meaning": item.business_meaning,
                    }
                    for item in (result.entity_relationships or [])
                ]
                logger.info(
                    "Inferred %d entity-level relationship(s)", len(entity_rels)
                )
            else:
                logger.warning(
                    "LLM returned None — no entity-level relationships inferred"
                )

        except Exception:
            logger.exception(
                "Entity relationship inference failed — "
                "falling back to physical relationships only"
            )

    # --- Store results -------------------------------------------------------
    state.entity_relationships = {
        "physical_relationships": physical,
        "entity_relationships": entity_rels,
    }
    return state
