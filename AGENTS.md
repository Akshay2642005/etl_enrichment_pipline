# ETL Enrichment Pipeline — AGENTS.md

## Project overview

AI-powered pipeline that ingests raw database metadata (JSON, SQL DDL, or live DB) and enriches it with business context via a single LLM call + rule-based passes (LangGraph). Output is written to `output/enriched_metadata.json`.

## Package manager & Python

- **uv** (required). Never pip. `uv sync` installs everything (editable install of `src/`).
- Python **3.13+** via `.python-version`.
- Dependencies in `pyproject.toml`, lockfile at `uv.lock`.

## Key commands

```bash
uv sync                     # install all deps (including dev: pytest, ruff)
uv run main.py              # start API server (FastAPI on :8000, auto-reload)
uv run main.py pipeline <file>   # run enrichment from a raw_metadata JSON
uv run main.py --sql-file <path> # parse SQL DDL -> pipeline
uv run main.py --db-connect      # interactive DB extraction + pipeline
uv run pytest                     # all tests
uv run pytest tests/test_pipeline.py::TestRawJsonToCanonicalSchema  # single class
uv run pytest -k "test_name"     # single test
uv run ruff check src/            # lint
uv run uvicorn main:app           # start API directly (same as uv run main.py)
```

> **Single server**: NL2SQL, quality, and insights services now run on a single FastAPI
> server (port 8000), not separate processes.  The standalone ``nl2sql_app.py`` was
> removed as part of that consolidation.

No Makefile, no justfile, no pre-commit hooks.

## Architecture

```
main.py                           # CLI entry point (api / pipeline, or nl2sql subcommand)
src/etl_enrichment_pipeline/
  api/
    main.py                       # FastAPI app (all services: enrich, NL2SQL, quality, insights)
    shared_state.py               # Lazy singletons: metadata, embedding_service, vector_store, graph_store
  agents/                         # 1 enrichment node + rule engine
    __init__.py                    # Lazy imports (PEP 562 __getattr__) to avoid circular deps
    extraction_agent.py           # PostgreSQL, MySQL, SQL Server, Oracle, SQLite extraction
    ddl_parser.py                 # SQL DDL -> raw JSON (sqlglot + simple-ddl-parser)
    enrichment_agent.py           # **Single** enrichment node: RuleEngine + one LLM call
    rule_engine.py                # YAML-driven rule-based classification (no LLM)
    (old per-agent files left on disk but not imported)
  core/
    pipeline.py                   # StateGraph builder + JSON adapter + runner
    orchestrator.py               # SQL/database bridge functions
    llm.py                        # ChatOpenAI factory (env-configured)
  models/
    canonical.py                  # CanonicalSchema, TableSchema, ColumnSchema, etc.
    pipeline_state.py             # PipelineState + type aliases
    final_output.py               # FinalOutput (11-section output shape)
    agent_outputs.py              # Consolidated EnrichmentOutput model (single LLM call)
  rules/                          # YAML rule files
    pii_rules.yaml
    semantic_type_rules.yaml
    pattern_rules.yaml
config/                           # DB connector YAML configs (port defaults, drivers)
src/etl_enrichment_pipeline/config/ # (duplicate) Global + per-DB configs
tests/
  conftest.py                     # Fixtures: minimal_canonical_schema, empty_pipeline_state
  test_pipeline.py                # Pipeline logic, JSON adapter, SQL/DB bridges
  test_api.py                     # FastAPI /health
  test_models.py                  # Pydantic roundtrip + import checks
```

### LangGraph pipeline (linear, 2 nodes)

`load_json → enrichment → END`

The single `enrichment` node runs RuleEngine (fast, no LLM) for PII/semantic type detection, then one LLM call for all remaining enrichment (descriptions, business roles, domains, entities, use cases, etc.), then rule-based pattern detection and validation. Each node accepts `PipelineState` and returns `PipelineState`. All nodes are wrapped with logging in `build_pipeline()`.

## LLM configuration

The pipeline uses `ChatOpenAI` from langchain-openai regardless of provider. Configured via `.env`:

```env
OPENAI_API_KEY="ollama"           # use "ollama" for Ollama; real key for OpenAI/OpenRouter/Groq/Azure
OPENAI_BASE_URL="http://localhost:11434/v1"  # omit for OpenAI default
LLM_MODEL="qwen2.5:3b"
LLM_TIMEOUT=120
```

`.env` is auto-loaded from project root by `core/llm.py`. See `.env.template` for presets.

**Key**: `OPENAI_API_KEY` is always the env var used, even for non-OpenAI providers. `temperature=0`, `max_retries=2`.

## Pipeline entry points

| Function | Source | Description |
|---|---|---|
| `run_pipeline(path)` | `core/pipeline.py` | Load JSON file → run pipeline → return dict |
| `run_pipeline_from_raw_json(dict, source_label)` | `core/pipeline.py` | Raw dict → pipeline (no disk I/O) |
| `run_pipeline_from_dict` | alias | Same as above |
| `run_pipeline_from_sql(file, ...)` | `core/orchestrator.py` | DDL file → ddl_to_json → pipeline |
| `run_pipeline_from_db(system_name, ...)` | `core/orchestrator.py` | Live DB → extraction_agent → pipeline |

Output always written to `output/enriched_metadata.json` by `main.py`.

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/v1/nl2sql/health` | NL2SQL sub-service health |
| POST | `/api/v1/nl2sql/generate` | Natural language → SQL generation |
| GET | `/api/v1/quality/health` | Quality sub-service health |
| POST | `/api/v1/quality/assess` | Assess quality of enriched metadata |
| GET | `/api/v1/insights/health` | Insights sub-service health |
| POST | `/api/v1/insights/generate` | Generate insights from enriched metadata |
| POST | `/enrich` | Accept raw metadata JSON body, run pipeline, return enriched result |

All sub-services share a consolidated `shared_state.py` module for lazy singletons
(metadata, embedding_service, vector_store, graph_store).  Store initialization is
gracefully degraded — each store initializes independently; failures set that store
to ``None`` rather than crashing the server.

`POST /enrich` writes body to a tempfile, calls `run_pipeline()`, cleans up the tempfile.

## Data flow

```
Input (JSON / SQL DDL / DB credentials)
  → raw_json_to_canonical_schema()  → CanonicalSchema (Pydantic)
  → PipelineState.canonical_schema
  → LangGraph.invoke(state)
  → assemble_final_output(state)    → FinalOutput.model_dump()
  → output/enriched_metadata.json
```

## Input JSON format (raw metadata)

```json
{
  "database_type": "postgresql",
  "schema": "public",
  "tables": [
    {
      "table_name": "attendance",
      "columns": [
        {"column_name": "id", "data_type": "integer", "nullable": false}
      ],
      "constraints": [
        {"constraint_name": "attendance_pkey", "constraint_type": "PRIMARY KEY", "column_name": "id"}
      ],
      "relationships": [
        {"child_column": "dept_id", "parent_table": "department", "parent_column": "id"}
      ]
    }
  ]
}
```

## Database extraction

Supported types: `postgres`, `mysql`, `mariadb`, `sqlserver`, `oracle`, `sqlite`.

- PostgreSQL: `psycopg2` — queries `information_schema` in `public` schema.
- MySQL/MariaDB: `pymysql` — queries `information_schema` for the database.
- Credentials from `.env` variables (`DB_CREW_*`, `DB_GROUND_*`) or interactive prompt.
- Extraction writes raw JSON to `sql_json/` with timestamped filenames.
- **Only one active production config**: "Crew Management System" (PostgreSQL). Others are commented out in `src/.../config/config_postgres.py`.
- The root `config/*.yaml` files provide port/driver defaults for interactive mode.

## Important quirks & gotchas

- **Circular imports**: `agents/__init__.py` uses lazy `__getattr__` to avoid circular imports between `agents.*` and `core.*`. Import agent node functions from `etl_enrichment_pipeline.agents`, not from individual agent modules under `agents/` when possible.
- **`sqlj_son` vs `sql_json`**: The README references `sqlj_son/` (typo). The actual directory is `sql_json/`. Default paths in `main.py` use `sql_json/`.
- **Duplicate config_global.py**: Exists at both `config/config_global.py` and `src/.../config/config_global.py`. The `main.py` and `core/llm.py` import from different paths.
- **Log level**: Read from `config/config_global.py` → `GLOBAL_PIPELINE["log_level"]` at startup by `main.py.setup_logging()`.
- **LangSmith tracing is ON**: `.env` has active LangSmith credentials (`LANGSMITH_*`). Traces appear at https://smith.langchain.com.
- **SQL injection in extraction_agent.py**: DB extraction uses f-string SQL interpolation, not parameterized queries. Only for internal/dev databases — do not expose to untrusted input.
- **`extraction_node()` is not implemented**: `extraction_agent.py` has a stub that raises `NotImplementedError`. Extraction is handled outside the LangGraph pipeline via `run_pipeline_from_raw_json`.
- **View parsing**: `raw_json_to_canonical_schema()` now parses the `"views"` key in input JSON into `ViewSchema` objects with columns and definitions.
- **API /enrich write to tempfile**: The endpoint serializes the request body to a tempfile on disk, then calls `run_pipeline()` (which reads it back). Not a streaming/zero-copy path.
- **pytest xfail / integration**: No integration test markers. Tests mock LangGraph/LLM calls. Live DB tests require actual database access — none are automated.
- **Relationship key naming**: Raw metadata JSON uses `child_table`/`child_column`/`parent_table`/`parent_column` for relationships (see Input JSON format above). The canonical model stores them as `from_table`/`from_column`/`to_table`/`to_column`. All code paths (`embedding_service`, `context_builder`, `graph_store`) now normalise both formats — do NOT rely on a single key naming convention.
- **Store connection timeouts**: `VectorStore` (asyncpg) and `GraphStore` (Neo4j) have 5s connection timeouts. When a store is unavailable, its reference is set to `None` and the context builder skips vector/graph queries gracefully rather than hanging.

## Test conventions

- `conftest.py` provides `minimal_canonical_schema` and `empty_pipeline_state` fixtures.
- Pipeline tests use `monkeypatch` to mock `build_pipeline()` (avoids LLM calls).
- `test_models.py` verifies `enrichment_node` and `RuleEngine` are importable.
- `test_api.py` uses FastAPI `TestClient`.

## Ruff (linting)

- Target: `py313`
- Rules: `E`, `F`, `I`, `N`, `W`, `UP`, `B`, `SIM`
- Per-file: `src/**/__init__.py` → `F401` ignored (unused imports for re-exports)
- No formatter config (use default `ruff format` or omit)
