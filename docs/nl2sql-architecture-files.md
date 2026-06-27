# NL2SQL Feature — File Inventory

## Overview
This document lists every file involved in the NL2SQL (Natural Language to SQL) feature,
organized by architectural layer. Each entry includes the file path, its role, and how
it connects to the rest of the system.

---

## 1. Entry Points & Server

| File | Role |
|---|---|
| `main.py` | Project entry point. `run_nl2sql_api()` starts uvicorn on port 8001. Also handles enrichment pipeline CLI commands. |
| `src/etl_enrichment_pipeline/api/nl2sql_app.py` | **FastAPI application definition.** Creates the `app` object, attaches the lifespan (loads `.env`, initialises stores, populates data), and registers the router. **Fixed: added `load_dotenv()` here.** |
| `src/etl_enrichment_pipeline/api/nl2sql_service.py` | **API router and request handler.** Defines Pydantic models (`NL2SQLRequest`, `NL2SQLResponse`), singleton service lifecycle (`_ensure_stores_initialized()`), and the POST `/api/v1/nl2sql` + GET `/health` endpoints. |
| `src/etl_enrichment_pipeline/api/main.py` | Enrichment pipeline API server (port 8000) — separate process from NL2SQL. |
| `pyproject.toml` | Project metadata, dependencies (including `langchain-openai`, `asyncpg`, `neo4j`, `sentence-transformers`). |

## 2. Core Services

| File | Role |
|---|---|
| `src/etl_enrichment_pipeline/core/store_loader.py` | **Bridge between enrichment pipeline and stores.** Reads `enriched_metadata.json`, generates embeddings via `EmbeddingService`, upserts into pgvector via `VectorStore`, loads graph into Neo4j via `GraphStore`. Called during server lifespan startup. |
| `src/etl_enrichment_pipeline/core/vector_store.py` | **pgvector client.** Connection pooling via `asyncpg`, HNSW index creation, `upsert_embeddings()` (INSERT ON CONFLICT DO UPDATE), `search_similar()` (cosine distance via `<=>` operator). Includes `_parse_dsn()` to handle Windows `[Errno 22]` SSL issue. |
| `src/etl_enrichment_pipeline/core/graph_store.py` | **Neo4j graph client.** Async driver, `initialize_schema()` (creates uniqueness constraints), `load_schema()` (creates Table/Column/Entity nodes with relationships), `find_join_paths()` (BFS traversal over FK_TO edges up to `max_hops`). |
| `src/etl_enrichment_pipeline/core/embedding_service.py` | **Sentence-transformers embedding.** Loads `BAAI/bge-small-en-v1.5` model. `embed_schema_objects(metadata)` generates 384-dim embeddings for all tables, columns, and relationships. `generate_embeddings(texts)` used during query time to embed user questions. |
| `src/etl_enrichment_pipeline/core/context_builder.py` | **Schema context assembly.** `build_context(question, vector_store, graph_store)` orchestrates: embed question → vector search tables/columns/relationships → extract matched table names → graph traversal for join paths → deduplicate & enrich from metadata → return `SchemaContext`. `format_prompt(context)` produces LLM-ready prompt text. |
| `src/etl_enrichment_pipeline/core/sql_validator.py` | **Generated SQL validation.** Validates generated SQL against the enriched metadata — checks that table names, column names, and relationships exist. Produces a confidence score. |

## 3. LLM Integration

| File | Role |
|---|---|
| `src/etl_enrichment_pipeline/core/llm.py` | **LLM factory.** Loads `.env`, returns a configured `ChatOpenAI` instance from `langchain-openai`. Reads `LLM_MODEL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_TIMEOUT` from environment. |
| `src/etl_enrichment_pipeline/agents/nl2sql_generator.py` | **SQL generator agent.** Uses LangChain `with_structured_output(GenerationResult, method='function_calling')` to produce deterministic SQL. Contains the system prompt with SQL generation rules and example queries. Handles graceful degradation (returns empty result on failure). |

## 4. Enrichment Pipeline Agents (upstream data preparation)

| File | Role |
|---|---|
| `src/etl_enrichment_pipeline/core/pipeline.py` | Runs the full enrichment pipeline: DDL parse → extraction agents → semantic enrichment → metadata output. |
| `src/etl_enrichment_pipeline/core/orchestrator.py` | Orchestrates pipeline execution steps. |
| `src/etl_enrichment_pipeline/agents/extraction_agent.py` | Extracts raw schema from database connections or SQL files. |
| `src/etl_enrichment_pipeline/agents/ddl_parser.py` | Parses SQL DDL statements into structured metadata. |
| `src/etl_enrichment_pipeline/agents/description_agent.py` | Generates human-readable descriptions for tables and columns. |
| `src/etl_enrichment_pipeline/agents/semantic_type_agent.py` | Assigns semantic types (e.g., `PERSON_NAME`, `EMAIL`, `DATE`) to columns. |
| `src/etl_enrichment_pipeline/agents/domain_agent.py` | Assigns business domain categories to tables. |
| `src/etl_enrichment_pipeline/agents/business_role_agent.py` | Determines business roles for tables. |
| `src/etl_enrichment_pipeline/agents/entity_discovery_agent.py` | Discovers business entities from table groupings. |
| `src/etl_enrichment_pipeline/agents/relationship_intelligence_agent.py` | Identifies entity-level business relationships. |
| `src/etl_enrichment_pipeline/agents/use_case_agent.py` | Generates business use cases for schema objects. |
| `src/etl_enrichment_pipeline/agents/sample_query_agent.py` | Generates sample SQL queries for discovered patterns. |
| `src/etl_enrichment_pipeline/agents/validation_agent.py` | Validates enriched metadata consistency. |
| `src/etl_enrichment_pipeline/agents/rule_engine.py` | Applies pattern-based rules for type detection. |
| `src/etl_enrichment_pipeline/agents/pattern_detection_agent.py` | Detects naming and structural patterns. |

## 5. Data Models

| File | Role |
|---|---|
| `src/etl_enrichment_pipeline/models/canonical.py` | Canonical data models — raw metadata structure after extraction. |
| `src/etl_enrichment_pipeline/models/agent_outputs.py` | Structured output schemas for each enrichment agent. |
| `src/etl_enrichment_pipeline/models/pipeline_state.py` | Pipeline execution state tracking. |
| `src/etl_enrichment_pipeline/models/final_output.py` | Final enriched metadata schema (what ends up in `enriched_metadata.json`). |

## 6. Configuration

| File | Role |
|---|---|
| `.env` | **Runtime configuration.** Database credentials (`PGVECTOR_DSN`, `NEO4J_URI/USER/PASSWORD`), LLM settings (`LLM_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`), embedding model (`EMBEDDING_MODEL`), metadata path (`METADATA_PATH`). |
| `config/config_global.py` | Global pipeline configuration constants. |
| `config/config_postgres.py` | PostgreSQL-specific connection configs. |
| `config/postgres.yaml` | Default PostgreSQL connection parameters. |
| `src/etl_enrichment_pipeline/rules/semantic_type_rules.yaml` | Rules for semantic type detection. |
| `src/etl_enrichment_pipeline/rules/pii_rules.yaml` | Rules for PII (personally identifiable information) detection. |
| `src/etl_enrichment_pipeline/rules/pattern_rules.yaml` | Rules for naming pattern detection. |

## 7. Data Files

| File | Role |
|---|---|
| `output/enriched_metadata.json` | **Input to the NL2SQL service.** Contains 30 tables, 121 columns, 31 FK relationships, enriched with descriptions, semantic types, domains, entities. Loaded into pgvector and Neo4j at server startup. |
| `output/parsed_schema.json` | Intermediate parsed schema from DDL/extraction (before enrichment). |
| `sql_json/postgres_crew_*.json` | Raw extracted metadata from the source PostgreSQL database. |
| `sql_json/raw_from_ddl_sample_schema.json` | Raw metadata extracted from sample DDL files. |

## 8. Tests

| File | Role |
|---|---|
| `tests/unit/test_nl2sql_generator.py` | Unit tests for `NL2SQLGenerator` — prompt formatting, generation result parsing, graceful degradation. |
| `tests/integration/test_nl2sql_pipeline.py` | Integration test for the full NL2SQL pipeline — vector search → graph traversal → context building → SQL generation. |
| `tests/unit/test_vector_store.py` | Unit tests for pgvector client (connection, upsert, search). |
| `tests/unit/test_graph_store.py` | Unit tests for Neo4j client (schema creation, data loading, BFS join paths). |
| `tests/unit/test_context_builder.py` | Unit tests for context assembly logic (deduplication, enrichment, metadata lookups). |
| `tests/unit/test_embedding_service.py` | Unit tests for embedding generation. |
| `tests/unit/test_sql_validator.py` | Unit tests for SQL validation against enriched metadata. |

## 9. Scripts

| File | Role |
|---|---|
| `scripts/generate_embeddings.py` | Standalone script to pre-generate embeddings for enriched metadata (alternative to lazy generation at server startup). |

---

## Data Flow Diagram

```
User Question (natural language)
        │
        ▼
┌───────────────────┐     ┌──────────────────────┐
│  nl2sql_app.py     │     │  .env (credentials)  │
│  (FastAPI server)  │────▶│                      │
│  port 8001         │     │  PG + Neo4j + LLM    │
└────────┬──────────┘     └──────────────────────┘
         │
         ▼
┌───────────────────┐
│ nl2sql_service.py  │  POST /api/v1/nl2sql
│  _ensure_stores    │
│  _get_context_     │
│  builder()...      │
└────────┬──────────┘
         │
    ┌────┴──────────────────────────────┐
    │                                   │
    ▼                                   ▼
┌──────────────────┐           ┌──────────────────┐
│ context_builder   │           │  nl2sql_generator │
│ .build_context()  │──────────▶│  .generate()     │
│                   │  Schema   │                  │
│ 1. embed question │  Context  │ LLM → SQL +     │
│ 2. vector search  │           │ confidence       │
│ 3. graph traverse │           └────────┬─────────┘
│ 4. deduplicate    │                    │
└────────┬─────────┘                     │
         │                               │
         ▼                               ▼
┌──────────────────┐           ┌──────────────────┐
│  vector_store.py  │           │  llm.py (factory)│
│  (pgvector)       │           │  ChatOpenAI      │
│  search_similar() │           │  → Ollama        │
└──────────────────┘           │  → Cloud Model    │
                                └──────────────────┘
┌──────────────────┐
│  graph_store.py   │  store_loader.py (startup)
│  (Neo4j)          │  loads enriched_metadata.json
│  find_join_paths()│  → EmbeddingService → VectorStore
└──────────────────┘  → GraphStore
```

## Key Connections

1. **Server startup** (`nl2sql_app.py` → `nl2sql_service.py` → `store_loader.py`):
   - Loads `.env`, creates singleton services, populates pgvector + Neo4j from `enriched_metadata.json`

2. **Request flow** (`nl2sql_service.py` → `context_builder.py` → `vector_store.py` + `graph_store.py`):
   - Embeds user question → searches pgvector for similar schema → traverses Neo4j for join paths → assembles context

3. **SQL generation** (`nl2sql_generator.py` → `llm.py` → Ollama cloud):
   - Formats context as LLM prompt → calls `ChatOpenAI` via LangChain structured output → returns `GenerationResult`

4. **Data population** (`store_loader.py` → `embedding_service.py` + `vector_store.py` + `graph_store.py`):
   - Generates 186 embeddings → upserts to pgvector → loads 162 nodes into Neo4j
