# Draft: Agents Enrichment Implementation

## Intent
Implement all AI enrichment agents (Phases 2-4 of master plan) to process `sqlj_son/raw_metadata.json` through a LangGraph pipeline, using LangChain + OpenAI for LLM-based enrichment.

## User Decisions
- **LLM Provider**: LangChain OpenAI (API key via OPENAI_API_KEY env var)
- **Extraction Agent**: NOT created — `sqlj_son/raw_metadata.json` IS the extraction output. A JSON adapter converts it to CanonicalSchema in the pipeline.
- **Pipeline**: Wire LangGraph StateGraph in `core/pipeline.py`
- **Validation**: Lenient — collect issues, never block output
- **No new input files**: Only `sqlj_son/raw_metadata.json`
- **No new code files**: Modify existing stubs only

## Current Project State
### ✅ Complete
- `models/canonical.py` — CanonicalSchema, TableSchema, ColumnSchema, RelationshipSchema, etc.
- `models/agent_outputs.py` — All 11 agent output models
- `models/pipeline_state.py` — PipelineState with 13 fields + type aliases
- `models/final_output.py` — FinalOutput with all 11 sections
- `rules/pii_rules.yaml`, `semantic_type_rules.yaml`, `pattern_rules.yaml`
- `config/config_global.py` — GLOBAL_PIPELINE settings
- `api/main.py` — FastAPI app with /health
- `tests/test_models.py`, `tests/test_api.py`, `tests/conftest.py`

### ⚠️ Stubs (raise NotImplementedError)
All under `src/etl_enrichment_pipeline/agents/`:
- description_agent.py, business_role_agent.py, domain_agent.py
- semantic_type_agent.py, entity_discovery_agent.py, relationship_intelligence_agent.py
- use_case_agent.py, sample_query_agent.py, pattern_detection_agent.py
- validation_agent.py, rule_engine.py

### ❌ Problematic
- `agents/__init__.py` imports `extraction_node` from non-existent `extraction_agent.py` — must fix
- `core/pipeline.py` — `build_pipeline()` returns None
- Dependencies not installed (langchain, langgraph, openai, fastapi, httpx, sqlglot, simple-ddl-parser)

### Input
`sqlj_son/raw_metadata.json` — PostgreSQL aviation schema with 28 tables across HR, flight ops, baggage, equipment, infrastructure domains

## Design

### Pipeline Flow (in order)
1. **load_json** (in pipeline.py) — Read raw_metadata.json → CanonicalSchema → PipelineState
2. **description_node** — LLM generates table/column descriptions
3. **business_role_node** — LLM classifies tables (master_data, transactional, etc.)
4. **domain_node** — LLM detects business domain per table
5. **semantic_type_node** — RuleEngine first → LLM fallback for columns
6. **entity_discovery_node** — LLM converts tables to business entities
7. **relationship_intelligence_node** — FK relationships + LLM for business meaning
8. **use_case_node** — LLM generates use cases
9. **sample_query_node** — LLM generates SQL queries
10. **pattern_detection_node** — Rule-based YAML pattern matching
11. **validation_node** — Rule-based checks (missing PKs, low confidence, etc.)
12. **assemble_final** — Gather all into FinalOutput JSON

### Agent Implementation Pattern
Each agent node:
```python
def some_node(state: PipelineState) -> PipelineState:
    schema = state.canonical_schema
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    # ... enrichment logic ...
    state.some_field = result
    return state
```

### JSON Adapter (raw_metadata.json → CanonicalSchema)
- database_type → database_info.vendor
- schema → database_info.name
- tables[].table_name → TableSchema.table_name
- tables[].columns[].column_name + data_type + nullable → ColumnSchema
- tables[].constraints where PRIMARY KEY → ColumnSchema.is_primary_key = True
- tables[].relationships → RelationshipSchema entries

### API
- POST /enrich — Accept raw_metadata.json, run pipeline, return final output

## Required env
- OPENAI_API_KEY in environment or .env

## Effort
Medium — 11 agent stubs to implement + pipeline wiring + API + tests
Risk: Low — all agents are additive, existing code unaffected
