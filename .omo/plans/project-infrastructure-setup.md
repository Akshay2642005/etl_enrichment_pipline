# project-infrastructure-setup - Work Plan

## TL;DR (For humans)
<!-- Fill this LAST, after the detailed plan below is written, so it summarizes the REAL plan. -->
<!-- Plain English for a non-engineer: NO file paths, NO todo numbers, NO wave/agent/tool names. -->

**What you'll get:** A fully set-up Python project for the ETL Schema Intelligence platform. Uses `uv` for package management, has all dependencies installed (LangGraph, Pydantic, FastAPI, sqlglot, etc.), a clean `src/` folder structure, placeholder files for all 11 AI agents, Pydantic v2 data models matching the architecture plan, a health-check API endpoint, YAML rule files, unit tests, and linting/formatting configured.

**Why this approach:** The project was a single script with no package manager. The master plan defines a complex multi-agent architecture. Setting up the infrastructure properly now — with `uv`, `src-layout`, Pydantic models, and a modular structure — prevents the project from becoming unmanageable as agents are built. Existing code is migrated into the new structure, not rewritten.

**What it will NOT do:** No AI logic is written, no real API endpoints beyond a health check, no database or Docker, no CI/CD, no agent orchestration wiring — pure infrastructure setup only.

**Effort:** Medium (~10-12 tasks across 7 waves)
**Risk:** Low — mostly file creation and dependency installs. The only risk is `uv init` flag compatibility on Windows, verified in the first step.
**Decisions to sanity-check:**
1. Package name `etl_enrichment_pipeline` (fixed typo from repo name)
2. `psycopg2-binary` instead of `psycopg2` (Windows compat)
3. Old `enrichment/` directory deleted (agents now under `src/.../agents/`)
4. Root `extractor.py` kept as a thin CLI shim

Your next move: After reading the full plan, either approve and start work, or request a high-accuracy review first.

---

> TL;DR (machine): Medium effort, Low risk. uv init + src-layout + deps + Pydantic models + 11 agent stubs + YAML rules + FastAPI skeleton + tests + linting. 10 todos, 7 waves, 1 final verification.

## Scope
### Must have
1. Initialize uv-managed Python project (`pyproject.toml`, `.python-version`, `uv.lock`, `.venv`)
2. Create `src/etl_enrichment_pipeline/` package with src-layout: `models/`, `agents/`, `api/`, `rules/`, `config/`, `core/` subpackages
3. Implement Pydantic v2 models: `CanonicalSchema`, `PipelineState`, `FinalOutput`, agent-specific output types (with full field specs)
4. Create agent stubs (11 agents + rule_engine + pipeline orchestrator) with LangGraph node-compatible signatures (`Callable[[PipelineState], PipelineState]`), all raising `NotImplementedError`
5. Create YAML rule files: `pii_rules.yaml`, `semantic_type_rules.yaml`, `pattern_rules.yaml` (3+ entries each)
6. FastAPI skeleton: `src/etl_enrichment_pipeline/api/main.py` with `GET /health` returning `200 {"status": "ok", "service": "etl-enrichment-pipeline", "version": "0.1.0"}`
7. Refactor existing `extractor.py` → `src/etl_enrichment_pipeline/agents/extraction_agent.py` (proper module), keep root `extractor.py` as a thin CLI shim
8. Refactor existing `config/` → `src/etl_enrichment_pipeline/config/` with updated import paths
9. Install ALL dependencies via `uv add`: langgraph, langchain-core, langchain-openai, pydantic, fastapi, uvicorn, sqlglot, simple-ddl-parser, structlog, pyyaml, psycopg2-binary, mysql-connector-python, httpx, pytest, pytest-cov
10. `tests/` directory with `conftest.py`, a sample test for `CanonicalSchema` instantiation + JSON roundtrip
11. `ruff` configuration in `pyproject.toml` (select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"])
12. `.gitignore` for `.venv/`, `__pycache__/`, `.codegraph/`, `connector_output.json`, `*.pyc`, `.ruff_cache/`
13. `.omo/evidence/` directory for QA artifacts
14. Delete the old empty `enrichment/` directory (agents now live under `src/etl_enrichment_pipeline/agents/`)

### Must NOT have (guardrails, anti-slop, scope boundaries)
- ❌ No agent implementation logic (no LLM calls, no prompts, no business rules)
- ❌ No LangGraph workflow wiring beyond stub function signatures
- ❌ No real YAML rule engine parsing logic — only the stub + example rule files
- ❌ No real API endpoints beyond `GET /health`
- ❌ No database schema or migrations (PostgreSQL is future)
- ❌ No Docker or CI/CD configuration
- ❌ No existing code deletion — root `extractor.py` is kept as a CLI shim, content moves
- ❌ Old `enrichment/` directory IS deleted (replaced by `src/.../agents/`)
- ❌ No CLI entry point (`[project.scripts]`) — deferred to later phase
- ❌ No `structlog` configuration module — deferred to agent wiring phase (Phase 1 proper)
- ❌ No production deployment concerns — dev-only setup

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: tests-after + pytest (the sample test validates models are buildable; infrastructure verification is by import + command success)
- Evidence: .omo/evidence/task-<N>-project-infrastructure-setup.txt
- Every todo has agent-executable acceptance criteria: a single `uv run <command>` that exits 0
- Final verification runs ALL checks in parallel after todos complete

## Execution strategy

### Branch strategy
- Create branch `feat/infrastructure-setup` from current `plan/enrichment_master_plan`
- One atomic commit per wave
- Final commit message: `feat(infra): initialize uv project with src-layout, model stubs, agent stubs, and API skeleton`

### Must check FIRST (discovery)
Before any code changes, run `uv init --package --lib` in a temp dir to verify the flags work with uv 0.9.9 on this Windows machine. If it fails, fall back to manual `pyproject.toml` creation.

### Parallel execution waves
> Target 5-8 todos per wave.
- **Wave 0** (1 todo): Discovery — verify uv init flags, test psycopg2-binary install, test uv add
- **Wave 1** (2 todos): Project scaffold — pyproject.toml, .python-version, .gitignore, ruff config, deps install
- **Wave 2** (3 todos): Package structure + Pydantic models — all directories, __init__.py files, CanonicalSchema, PipelineState, FinalOutput, agent output models
- **Wave 3** (2 todos): Agent stubs + pipeline — 11 agent files, rule_engine.py, pipeline.py
- **Wave 4** (2 todos): YAML rules + FastAPI skeleton — rule files, api/main.py
- **Wave 5** (2 todos): Refactor existing code — migrate extractor.py and config/, delete enrichment/, keep root shim
- **Wave 6** (2 todos): Tests + evidence — tests/ directory, conftest, sample test, .omo/evidence/

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 0. Discovery | — | 1 | — |
| 1. uv init scaffold | 0 | 2, 6 | — |
| 2. Dependencies install | 1 | 3, 4, 5 | — |
| 3. Package dirs + __init__ | 1 | 4, 5, 6 | — |
| 4. Pydantic models | 2, 3 | 5, 7 | — |
| 5. Agent stubs | 2, 3 | 8 | — |
| 6. YAML rule files | 1 | — | 4, 5 |
| 7. FastAPI skeleton | 2, 3 | — | 4, 5, 6 |
| 8. Refactor existing code | 2, 3 | 9 | 4, 5, 6, 7 |
| 9. Tests + evidence | 4, 5, 7, 8 | — | — |
| — | — | — | — |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->

### Wave 0 — Discovery

- [ ] 0. Verify uv init flags and dependency availability on this machine
  What to do / Must NOT do:
  - Create a temp directory, run `uv init --package --lib test-proj`, verify it creates `src/test_proj/`, `pyproject.toml`, `.python-version`, `.gitignore`. If it fails, document the working fallback flags (e.g., `uv init --package` alone, or manual pyproject.toml creation).
  - Run `uv add psycopg2-binary` in the temp project to confirm it installs without C compiler errors.
  - Run `uv add langgraph langchain-core pydantic fastapi uvicorn[standard] sqlglot structlog pyyaml` to confirm they resolve without conflicts.
  - Delete the temp directory when done.
  - Must NOT skip even if "obvious" — this is a mandatory platform compatibility check.
  Parallelization: Wave 0 | Blocked by: — | Blocks: 1
  References (executor has NO interview context - be exhaustive):
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Recommended Technology Stack (lines 141-280): full dependency list
  - Metis finding GAP 14: uv init --package --lib on existing codebase needs verification
  - Metis finding GAP 4: psycopg2 fails on Windows, use psycopg2-binary
  - Metis finding GAP 17: Python 3.14 pre-release risk
  Acceptance criteria (agent-executable):
  ```bash
  # All exit 0:
  uv lock --check  # in temp project
  uv run python -c "import langgraph; import langchain_core; import pydantic; import fastapi; import sqlglot; import structlog; import yaml; print('ALL DEPS OK')"
  ```
  QA scenarios: happy — all commands exit 0, no errors. failure — if uv init fails, document the fallback and manually create pyproject.toml content. Evidence: .omo/evidence/task-0-project-infrastructure-setup.txt
  Commit: N | (discovery — no code changed)

### Wave 1 — Project Scaffold

- [ ] 1. Initialize uv project with pyproject.toml, .python-version, .gitignore
  What to do / Must NOT do:
  - Run `uv init --package --lib --name etl-enrichment-pipeline --description "AI-powered ETL Schema Intelligence Platform" --python 3.13` in the repo root.
  - If this fails (existing files), manually create `pyproject.toml` with the content in References.
  - Create `.python-version` with `3.13.14` (exact version, not range — prevents picking up Python 3.14 pre-release).
  - Ensure `.gitignore` excludes: `.venv/`, `__pycache__/`, `*.pyc`, `.codegraph/`, `connector_output.json`, `.ruff_cache/`, `.pytest_cache/`, `*.egg-info/`, `dist/`, `build/`.
  - Must NOT overwrite existing `.git/` or `.codegraph/` directories.
  - Must NOT create `main.py` at root (uv init default) — delete if created.
  - Must NOT change `README.md`.
  Parallelization: Wave 1 | Blocked by: 0 | Blocks: 2, 3, 6
  References (executor has NO interview context - be exhaustive):
  - uv docs: "use uv init --package --lib for src-layout packaged projects"
  - Decision record: Python 3.13.14 pinned, psycopg2-binary replaces psycopg2
  - Metis finding GAP 14: verify uv init --package --lib works first (todo 0)
  - Metis finding GAP 17: pin .python-version to 3.13.14 exactly
  - Metis finding GAP 15: pyproject.toml metadata:
    ```toml
    [project]
    name = "etl-enrichment-pipeline"
    version = "0.1.0"
    description = "AI-powered ETL Schema Intelligence Platform"
    readme = "README.md"
    requires-python = ">=3.12"
    dependencies = []
    
    [build-system]
    requires = ["uv_build>=0.11.23,<0.12"]
    build-backend = "uv_build"
    
    [tool.ruff]
    target-version = "py313"
    
    [tool.ruff.lint]
    select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]
    
    [tool.ruff.lint.per-file-ignores]
    "src/**/__init__.py" = ["F401"]
    
    [tool.pytest.ini_options]
    minversion = "7.0"
    testpaths = ["tests"]
    ```
  Acceptance criteria (agent-executable):
  ```bash
  # All exit 0:
  Test-Path "pyproject.toml"
  Test-Path ".python-version"
  Test-Path ".gitignore"
  Get-Content ".python-version" | Select-String "3.13.14"
  uv lock --check
  ```
  QA scenarios: happy — all files exist with correct content, `uv lock --check` passes. failure — missing files or wrong content; verify by checking each file path. Evidence: .omo/evidence/task-1-project-infrastructure-setup.txt
  Commit: Y | feat(infra): initialize uv project with pyproject.toml, .python-version, .gitignore

- [ ] 2. Install all project dependencies via uv add
  What to do / Must NOT do:
  - Run the following uv add commands (in order, as one session):
    ```bash
    uv add langgraph langchain-core langchain-openai pydantic fastapi uvicorn[standard] sqlglot simple-ddl-parser structlog pyyaml psycopg2-binary mysql-connector-python httpx
    uv add --dev pytest pytest-cov ruff
    ```
  - Must NOT install `psycopg2` (use `psycopg2-binary` — Windows compat).
  - Must NOT install anything outside the tech stack from the master plan.
  - After install, verify importability of each package (see acceptance criteria).
  - Run `uv lock --check` to ensure lockfile consistency.
  Parallelization: Wave 1 | Blocked by: 1 | Blocks: 4, 5, 7, 8
  References (executor has NO interview context - be exhaustive):
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Recommended Technology Stack (lines 141-280)
  - Metis finding GAP 4: psycopg2-binary instead of psycopg2 on Windows
  - Metis finding GAP 5: simple-ddl-parser must be included as fallback parser
  - Decision record: psycopg2-binary for dev; production caveat documented in comments
  Acceptance criteria (agent-executable):
  ```bash
  uv run python -c "
  import langgraph
  import langchain_core
  import langchain_openai
  import pydantic
  import fastapi
  import sqlglot
  import simple_ddl_parser
  import structlog
  import yaml
  import httpx
  import pytest
  import ruff
  print('ALL DEPS IMPORT OK')
  "
  uv lock --check
  ```
  QA scenarios: happy — all imports succeed, lockfile is consistent. failure — any import fails, or uv lock reports inconsistency; diagnose and fix by removing conflicting deps and re-running. Evidence: .omo/evidence/task-2-project-infrastructure-setup.txt
  Commit: Y | feat(infra): install all project dependencies (langgraph, pydantic, fastapi, sqlglot, etc.)

### Wave 2 — Package Structure & Models

- [ ] 3. Create src/etl_enrichment_pipeline package structure with all subpackages
  What to do / Must NOT do:
  - Create the following directory structure with `__init__.py` in each:
    ```
    src/
    └── etl_enrichment_pipeline/
        ├── __init__.py          # version = "0.1.0"
        ├── models/
        │   ├── __init__.py      # re-export all models
        │   ├── canonical.py     # CanonicalSchema, TableSchema, ColumnSchema, etc.
        │   ├── pipeline_state.py # PipelineState (shared LangGraph state)
        │   ├── final_output.py  # FinalOutput
        │   └── agent_outputs.py # Per-agent output TypedDicts/BaseModels
        ├── agents/
        │   ├── __init__.py
        │   ├── extraction_agent.py
        │   ├── description_agent.py
        │   ├── business_role_agent.py
        │   ├── domain_agent.py
        │   ├── semantic_type_agent.py
        │   ├── entity_discovery_agent.py
        │   ├── relationship_intelligence_agent.py
        │   ├── use_case_agent.py
        │   ├── sample_query_agent.py
        │   ├── pattern_detection_agent.py
        │   ├── validation_agent.py
        │   └── rule_engine.py
        ├── api/
        │   ├── __init__.py
        │   └── main.py           # FastAPI app + /health endpoint
        ├── rules/
        │   ├── __init__.py
        │   ├── pii_rules.yaml
        │   ├── semantic_type_rules.yaml
        │   └── pattern_rules.yaml
        ├── config/
        │   ├── __init__.py
        │   ├── config_global.py
        │   ├── config_postgres.py
        │   └── config_mysql.py
        ├── core/
        │   ├── __init__.py
        │   └── pipeline.py       # LangGraph pipeline orchestrator stub
        └── py.typed              # PEP 561 marker file (empty, indicates typed package)
    ```
  - Every `__init__.py` should be non-empty where it provides exports.
  - Must NOT create any implementation logic in agent files — only stubs.
  - Must NOT create `src/etl_enrichment_pipeline/__main__.py` (no CLI yet).
  Parallelization: Wave 2 | Blocked by: 1 | Blocks: 4, 5, 7, 8
  References (executor has NO interview context - be exhaustive):
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Current Project Structure (lines 872-894): shows old structure
  - Decision record: src-layout, package name = etl_enrichment_pipeline
  - Metis finding GAP 3: enrichment/ deleted; agents/ under src/.../agents/
  - Metis finding GAP 2: extractor.py migration strategy — root file becomes CLI shim
  Acceptance criteria (agent-executable):
  ```bash
  # Verify all directories and __init__.py files exist
  $paths = @(
    "src/etl_enrichment_pipeline/__init__.py",
    "src/etl_enrichment_pipeline/models/__init__.py",
    "src/etl_enrichment_pipeline/agents/__init__.py",
    "src/etl_enrichment_pipeline/api/__init__.py",
    "src/etl_enrichment_pipeline/rules/__init__.py",
    "src/etl_enrichment_pipeline/config/__init__.py",
    "src/etl_enrichment_pipeline/core/__init__.py",
    "src/etl_enrichment_pipeline/py.typed"
  )
  foreach ($p in $paths) { if (!(Test-Path $p)) { Write-Error "Missing: $p"; exit 1 } }
  Write-Output "ALL DIRS OK"
  ```
  QA scenarios: happy — all 8+ paths exist. failure — any missing directory; recreate. Evidence: .omo/evidence/task-3-project-infrastructure-setup.txt
  Commit: Y | feat(infra): create src/etl_enrichment_pipeline package with all subpackages

- [ ] 4. Implement Pydantic v2 models (CanonicalSchema, PipelineState, FinalOutput, agent outputs)
  What to do / Must NOT do:
  - Create `src/etl_enrichment_pipeline/models/canonical.py` with these exact models:
    ```python
    from pydantic import BaseModel, Field
    from typing import Optional, Any
    
    class ColumnSchema(BaseModel):
        table_name: str
        column_name: str
        data_type: str
        max_length: Optional[int] = None
        is_nullable: bool = True
        is_primary_key: bool = False
        default_value: Optional[str] = None
    
    class TableSchema(BaseModel):
        table_name: str
        columns: list[ColumnSchema] = Field(default_factory=list)
        table_type: str = "TABLE"  # TABLE | VIEW
        description: Optional[str] = None
    
    class ViewSchema(BaseModel):
        view_name: str
        definition: str
        columns: list[ColumnSchema] = Field(default_factory=list)
    
    class IndexSchema(BaseModel):
        index_name: str
        table_name: str
        column_names: list[str] = Field(default_factory=list)
        is_unique: bool = False
    
    class FunctionSchema(BaseModel):
        function_name: str
        definition: str
        return_type: Optional[str] = None
    
    class ProcedureSchema(BaseModel):
        procedure_name: str
        definition: str
    
    class TriggerSchema(BaseModel):
        trigger_name: str
        table_name: str
        definition: str
        timing: str = ""   # BEFORE | AFTER
        event: str = ""    # INSERT | UPDATE | DELETE
    
    class RelationshipSchema(BaseModel):
        from_table: str
        from_column: str
        to_table: str
        to_column: str
        constraint_name: Optional[str] = None
    
    class DatabaseInfo(BaseModel):
        name: Optional[str] = None
        vendor: Optional[str] = None
        version: Optional[str] = None
    
    class CanonicalSchema(BaseModel):
        database_info: DatabaseInfo = Field(default_factory=DatabaseInfo)
        tables: list[TableSchema] = Field(default_factory=list)
        views: list[ViewSchema] = Field(default_factory=list)
        indexes: list[IndexSchema] = Field(default_factory=list)
        functions: list[FunctionSchema] = Field(default_factory=list)
        procedures: list[ProcedureSchema] = Field(default_factory=list)
        triggers: list[TriggerSchema] = Field(default_factory=list)
        relationships: list[RelationshipSchema] = Field(default_factory=list)
    ```
  - Create `src/etl_enrichment_pipeline/models/pipeline_state.py` with:
    ```python
    from pydantic import BaseModel, Field
    from typing import Optional, Any
    from .canonical import CanonicalSchema
    from .agent_outputs import (
        DescriptionMap, BusinessRoleMap, DomainResult, 
        SemanticTypeMap, EntityList, RelationshipList,
        UseCaseList, SampleQueryList, PatternList, ValidationReport
    )
    
    class PipelineState(BaseModel):
        raw_input: Optional[str] = None
        canonical_schema: Optional[CanonicalSchema] = None
        descriptions: Optional[DescriptionMap] = None
        business_roles: Optional[BusinessRoleMap] = None
        domains: Optional[DomainResult] = None
        semantic_types: Optional[SemanticTypeMap] = None
        entities: Optional[EntityList] = None
        entity_relationships: Optional[RelationshipList] = None
        use_cases: Optional[UseCaseList] = None
        sample_queries: Optional[SampleQueryList] = None
        patterns: Optional[PatternList] = None
        validation_report: Optional[ValidationReport] = None
        final_output: Optional[dict] = None
    ```
  - Create `src/etl_enrichment_pipeline/models/agent_outputs.py` with TypedDict/BaseModel definitions for each agent's output shape (matching master plan JSON examples).
  - Create `src/etl_enrichment_pipeline/models/final_output.py` matching master plan §Final Output Structure.
  - `src/etl_enrichment_pipeline/models/__init__.py` must re-export everything.
  - Must NOT add any business logic, validation, or serialization methods beyond what Pydantic provides by default.
  - Must NOT use `Any` where a concrete type is possible.
  Parallelization: Wave 2 | Blocked by: 2, 3 | Blocks: 5, 7, 9
  References (executor has NO interview context - be exhaustive):
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Canonical Schema Model (lines 764-781): JSON shape
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §LangGraph Design (lines 283-321): PipelineState fields
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Final Output Structure (lines 785-811): FinalOutput shape
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Agent Responsibilities (lines 325-637): per-agent output shapes
  - Metis finding GAP 7: field-level specs required
  Acceptance criteria (agent-executable):
  ```bash
  uv run python -c "
  from etl_enrichment_pipeline.models.canonical import CanonicalSchema, TableSchema, ColumnSchema
  from etl_enrichment_pipeline.models.pipeline_state import PipelineState
  from etl_enrichment_pipeline.models.agent_outputs import DescriptionMap, BusinessRoleMap
  from etl_enrichment_pipeline.models.final_output import FinalOutput
  
  # CanonicalSchema roundtrip
  s = CanonicalSchema()
  d = s.model_dump()
  s2 = CanonicalSchema.model_validate(d)
  assert s == s2
  
  # PipelineState roundtrip
  ps = PipelineState()
  pd = ps.model_dump()
  ps2 = PipelineState.model_validate(pd)
  assert ps == ps2
  
  print('ALL MODELS OK')
  "
  ```
  QA scenarios: happy — all models instantiate, serialize, and deserialize. failure — import error, validation error, or roundtrip mismatch. Evidence: .omo/evidence/task-4-project-infrastructure-setup.txt
  Commit: Y | feat(infra): implement Pydantic v2 models for CanonicalSchema, PipelineState, FinalOutput

### Wave 3 — Agent Stubs

- [x] 5. Create all agent stubs with LangGraph-compatible function signatures
  What to do / Must NOT do:
  - For each agent file in `src/etl_enrichment_pipeline/agents/`, create a module-level function with signature:
    ```python
    from etl_enrichment_pipeline.models.pipeline_state import PipelineState
    
    def <agent_name>_node(state: PipelineState) -> PipelineState:
        \"\"\"
        <Agent purpose from master plan>
        
        <One-line description of what this agent does>
        
        TODO: Implement in Phase <X>
        \"\"\"
        raise NotImplementedError("<agent_name>_node not yet implemented")
    ```
  - The 11 agents (matching master plan order):
    1. `extraction_agent.py` — extraction_node (already being migrated from extractor.py; this WILL have code)
    2. `description_agent.py` — description_node
    3. `business_role_agent.py` — business_role_node
    4. `domain_agent.py` — domain_node
    5. `semantic_type_agent.py` — semantic_type_node
    6. `entity_discovery_agent.py` — entity_discovery_node
    7. `relationship_intelligence_agent.py` — relationship_intelligence_node
    8. `use_case_agent.py` — use_case_node
    9. `sample_query_agent.py` — sample_query_node
    10. `pattern_detection_agent.py` — pattern_detection_node
    11. `validation_agent.py` — validation_node
  - Create `rule_engine.py` with a class:
    ```python
    from pydantic import BaseModel
    
    class RuleEngine(BaseModel):
        \"\"\"YAML-driven rule-based classification engine.
        
        Loads rules from YAML files and applies them without LLM calls.
        Covers: PII detection, audit patterns, soft delete, common semantic types.
        
        TODO: Implement in Phase 2/3 — load from src/etl_enrichment_pipeline/rules/*.yaml
        \"\"\"
        rules_dir: str = ""
        
        def classify(self, column_name: str, data_type: str) -> dict:
            raise NotImplementedError("RuleEngine.classify not yet implemented")
    ```
  - `agents/__init__.py` must export all node functions.
  - Must NOT include any LangGraph `StateGraph` wiring — that goes in `core/pipeline.py`.
  - Must NOT include any LLM calls, prompts, or business logic.
  - Extraction agent IS the exception: it gets the actual extractor logic migrated from root `extractor.py` (see todo 8).
  Parallelization: Wave 3 | Blocked by: 2, 3 | Blocks: 9
  References (executor has NO interview context - be exhaustive):
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Agent Responsibilities (lines 325-637): full spec for each agent
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §LangGraph Design (lines 283-321): Callable[[PipelineState], PipelineState] pattern
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Rule Engine (lines 639-700): YAML-driven classification
  - Metis finding GAP 6: must provide concrete stub pattern (done above)
  Acceptance criteria (agent-executable):
  ```bash
  uv run python -c "
  from etl_enrichment_pipeline.agents import (
      description_node, business_role_node, domain_node,
      semantic_type_node, entity_discovery_node, relationship_intelligence_node,
      use_case_node, sample_query_node, pattern_detection_node, validation_node,
      extraction_node
  )
  from etl_enrichment_pipeline.agents.rule_engine import RuleEngine
  re = RuleEngine()
  print(f'11 agents + RuleEngine OK: {len([extraction_node]) + 10} stubs')
  "
  ```
  QA scenarios: happy — all stubs import and are callable (even if they raise NotImplementedError). failure — import error, missing function. Evidence: .omo/evidence/task-5-project-infrastructure-setup.txt
  Commit: Y | feat(infra): create 11 agent stubs + RuleEngine with LangGraph-compatible signatures

### Wave 4 — Configuration & API

- [x] 6. Create YAML rule files with skeleton content
  What to do / Must NOT do:
  - Create `src/etl_enrichment_pipeline/rules/pii_rules.yaml`:
    ```yaml
    # PII / sensitive column detection rules (rule-based, no LLM)
    # format: column_name_pattern -> classification
    pii_columns:
      - pattern: "email"
        classification: "EMAIL"
        confidence: 0.95
      - pattern: "phone"
        classification: "PHONE"
        confidence: 0.95
      - pattern: "mobile"
        classification: "PHONE"
        confidence: 0.90
      - pattern: "aadhaar"
        classification: "GOVT_ID"
        confidence: 0.98
      - pattern: "pan"
        classification: "GOVT_ID"
        confidence: 0.98
      - pattern: "passport"
        classification: "GOVT_ID"
        confidence: 0.98
    ```
  - Create `src/etl_enrichment_pipeline/rules/semantic_type_rules.yaml`:
    ```yaml
    # Semantic type detection rules (rule-based, no LLM)
    # Column name patterns mapped to semantic types
    semantic_types:
      - pattern: "email"
        type: "EMAIL"
      - pattern: "phone|mobile|telephone"
        type: "PHONE"
      - pattern: "first_name|fname"
        type: "FIRST_NAME"
      - pattern: "last_name|lname"
        type: "LAST_NAME"
      - pattern: "dob|date_of_birth"
        type: "DATE_OF_BIRTH"
      - pattern: "country"
        type: "COUNTRY"
      - pattern: "city"
        type: "CITY"
      - pattern: "state|province"
        type: "STATE"
      - pattern: "status"
        type: "STATUS"
      - pattern: "created_at|updated_at"
        type: "TIMESTAMP"
    ```
  - Create `src/etl_enrichment_pipeline/rules/pattern_rules.yaml`:
    ```yaml
    # Schema pattern detection rules
    patterns:
      audit_trail:
        description: "Columns tracking creation and modification timestamps and users"
        indicators: ["created_at", "updated_at", "created_by", "updated_by"]
      soft_delete:
        description: "Rows are marked as deleted rather than removed"
        indicators: ["deleted_at", "is_deleted", "deleted_flag"]
      multi_tenancy:
        description: "Data is isolated by tenant identifier"
        indicators: ["tenant_id", "organization_id", "company_id"]
      versioning:
        description: "Rows track version history"
        indicators: ["version", "version_number", "revision"]
      state_machine:
        description: "Rows transition through defined states"
        indicators: ["status", "state", "lifecycle_stage"]
    ```
  - `rules/__init__.py` must export a `RULES_DIR` constant pointing to this directory.
  - Must NOT implement rule loading logic (that goes in `rule_engine.py` in Phase 2).
  - Must NOT include more than 10 entries per file — these are skeletons.
  Parallelization: Wave 4 | Blocked by: 1 | Blocks: — (independent of agents/models)
  References (executor has NO interview context - be exhaustive):
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Rule Engine (lines 639-700): YAML-driven PII, audit, soft delete, semantic type rules
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Common Semantic Types (lines 687-699): column patterns
  - Metis finding GAP 11: skeleton content must have 3+ entries per file
  Acceptance criteria (agent-executable):
  ```bash
  uv run python -c "
  import yaml
  from pathlib import Path
  rules_dir = Path('src/etl_enrichment_pipeline/rules')
  for f in ['pii_rules.yaml', 'semantic_type_rules.yaml', 'pattern_rules.yaml']:
      path = rules_dir / f
      assert path.exists(), f'Missing: {f}'
      data = yaml.safe_load(path.read_text())
      assert data is not None, f'Empty YAML: {f}'
      assert len(data) > 0, f'No top-level keys: {f}'
  print('ALL RULE FILES OK')
  "
  ```
  QA scenarios: happy — all 3 YAML files exist and parse correctly. failure — missing file, invalid YAML, empty file. Evidence: .omo/evidence/task-6-project-infrastructure-setup.txt
  Commit: Y | feat(infra): create YAML rule files for PII, semantic types, and pattern detection

- [x] 7. Create FastAPI skeleton with /health endpoint
  What to do / Must NOT do:
  - Create `src/etl_enrichment_pipeline/api/main.py`:
    ```python
    """ETL Schema Intelligence API — FastAPI application."""
    
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI(
        title="ETL Schema Intelligence",
        description="AI-powered Schema Intelligence Platform API",
        version="0.1.0",
    )
    
    @app.get("/health")
    async def health():
        return JSONResponse(
            content={
                "status": "ok",
                "service": "etl-enrichment-pipeline",
                "version": "0.1.0",
            },
            status_code=200,
        )
    
    # TODO: Add routers in Phase 5 (FastAPI Service)
    # - POST /schema/extract
    # - POST /schema/enrich
    # - GET  /schema/{id}
    ```
  - `api/__init__.py` must export the `app` object.
  - Must NOT add any routers, middleware, or CORS configuration.
  - Must NOT add any agent-triggering endpoints.
  Parallelization: Wave 4 | Blocked by: 2 | Blocks: 9
  References (executor has NO interview context - be exhaustive):
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §API Layer (lines 229-235): FastAPI
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Phase 5 (lines 858-868): API Service deferred
  - Metis finding GAP 10: /health endpoint contract specified
  Acceptance criteria (agent-executable):
  ```bash
  # Start server in background, hit /health, kill server
  uv run uvicorn etl_enrichment_pipeline.api.main:app --host 127.0.0.1 --port 18080 &
  $pid = $!
  Start-Sleep -Seconds 3
  $response = uv run python -c "
  import httpx
  r = httpx.get('http://127.0.0.1:18080/health')
  assert r.status_code == 200
  data = r.json()
  assert data['status'] == 'ok'
  assert data['service'] == 'etl-enrichment-pipeline'
  assert data['version'] == '0.1.0'
  print('HEALTH OK')
  "
  Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
  ```
  QA scenarios: happy — /health returns 200 with correct JSON body. failure — port conflict, wrong response, import error. Evidence: .omo/evidence/task-7-project-infrastructure-setup.txt
  Commit: Y | feat(infra): create FastAPI skeleton with /health endpoint

### Wave 5 — Existing Code Refactoring

- [x] 8. Refactor extractor.py and config/ into new package structure
  What to do / Must NOT do:
  - Move content from root `extractor.py` into `src/etl_enrichment_pipeline/agents/extraction_agent.py` as a proper module:
    - Wrap existing logic into an `extraction_node(state: PipelineState) -> PipelineState` function
    - Extract the database-connection logic into reusable functions: `extract_postgres_schema(creds, rules)`, `extract_mysql_schema(creds, rules)`
    - Return a `PipelineState` with `canonical_schema` populated
    - The function should raise `NotImplementedError` with a docstring about Phase 1 rework (the current extraction targets the old `connector_output.json` structure, not the new Pydantic models)
  - Move `config/` files into `src/etl_enrichment_pipeline/config/`:
    - Update all import paths: `from etl_enrichment_pipeline.config.config_global import ...`
    - Keep dict-based config as-is (refactoring to Pydantic config models is deferred)
  - Root `extractor.py` becomes a thin CLI shim:
    ```python
    #!/usr/bin/env python3
    \"\"\"ETL Enrichment Pipeline — CLI entry point.
    
    This file is a thin wrapper. The extraction logic has moved to:
        src/etl_enrichment_pipeline/agents/extraction_agent.py
    \"\"\"
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    
    if __name__ == "__main__":
        from etl_enrichment_pipeline.agents.extraction_agent import main as extract_main
        extract_main()
    ```
  - Delete the old empty `enrichment/` directory (agents now live under `src/.../agents/`).
  - Must NOT delete root `extractor.py` — keep as CLI shim.
  - Must NOT break the original `python extractor.py` invocation (it should still work via the shim).
  - Must NOT implement any new extraction features.
  Parallelization: Wave 5 | Blocked by: 2, 3 | Blocks: 9
  References (executor has NO interview context - be exhaustive):
  - Root `extractor.py` (lines 1-141): full source to migrate
  - `config/config_global.py`, `config/config_postgres.py`, `config/config_mysql.py`: config files to move
  - Metis finding GAP 2: extractor.py migration strategy = keep as CLI shim
  - Metis finding GAP 3: enrichment/ deleted
  - Metis finding GAP 18: import paths after migration
  Acceptance criteria (agent-executable):
  ```bash
  uv run python -c "
  from etl_enrichment_pipeline.agents.extraction_agent import extraction_node
  from etl_enrichment_pipeline.config.config_global import GLOBAL_PIPELINE, CONNECTOR_SETTINGS
  from etl_enrichment_pipeline.config.config_postgres import POSTGRES_DBS
  from etl_enrichment_pipeline.config.config_mysql import MYSQL_DBS
  assert len(POSTGRES_DBS) == 3
  assert len(MYSQL_DBS) == 4
  print('REFACTORED IMPORTS OK')
  "
  # Verify root shim exists and is executable
  Test-Path "extractor.py"
  ```
  QA scenarios: happy — imports work, config values intact, root shim exists. failure — import error, missing config keys, shim not found. Evidence: .omo/evidence/task-8-project-infrastructure-setup.txt
  Commit: Y | refactor(extractor): migrate extractor.py and config/ into src-layout package, keep root CLI shim

### Wave 6 — Tests & QA

- [x] 9. Create tests/ directory with conftest.py and sample test
  What to do / Must NOT do:
  - Create `tests/__init__.py` (empty)
  - Create `tests/conftest.py`:
    ```python
    """Shared fixtures for ETL Schema Intelligence tests."""
    import pytest
    from etl_enrichment_pipeline.models.canonical import (
        CanonicalSchema, TableSchema, ColumnSchema, RelationshipSchema
    )
    
    @pytest.fixture
    def minimal_canonical_schema():
        return CanonicalSchema(
            tables=[
                TableSchema(
                    table_name="patients",
                    columns=[
                        ColumnSchema(table_name="patients", column_name="patient_id", data_type="INTEGER", is_primary_key=True),
                        ColumnSchema(table_name="patients", column_name="name", data_type="VARCHAR"),
                        ColumnSchema(table_name="patients", column_name="email", data_type="VARCHAR"),
                    ]
                )
            ]
        )
    
    @pytest.fixture
    def empty_pipeline_state():
        from etl_enrichment_pipeline.models.pipeline_state import PipelineState
        return PipelineState()
    ```
  - Create `tests/test_models.py`:
    ```python
    """Tests for Pydantic v2 data models."""
    
    def test_canonical_schema_roundtrip(minimal_canonical_schema):
        """CanonicalSchema serializes and deserializes without data loss."""
        data = minimal_canonical_schema.model_dump()
        restored = type(minimal_canonical_schema).model_validate(data)
        assert restored == minimal_canonical_schema
    
    def test_canonical_schema_defaults():
        """CanonicalSchema can be created with no arguments."""
        from etl_enrichment_pipeline.models.canonical import CanonicalSchema
        schema = CanonicalSchema()
        assert schema.tables == []
        assert schema.views == []
        assert schema.relationships == []
    
    def test_pipeline_state_defaults(empty_pipeline_state):
        """PipelineState can be created with no arguments."""
        ps = empty_pipeline_state
        assert ps.raw_input is None
        assert ps.canonical_schema is None
        assert ps.final_output is None
    
    def test_all_agent_stubs_importable():
        """All 11 agent node functions and RuleEngine are importable."""
        from etl_enrichment_pipeline.agents import (
            extraction_node, description_node, business_role_node,
            domain_node, semantic_type_node, entity_discovery_node,
            relationship_intelligence_node, use_case_node, sample_query_node,
            pattern_detection_node, validation_node
        )
        from etl_enrichment_pipeline.agents.rule_engine import RuleEngine
        assert callable(extraction_node)
        re = RuleEngine()
        assert re.rules_dir == ""
    ```
  - Create `tests/test_api.py`:
    ```python
    """Tests for FastAPI skeleton."""
    from fastapi.testclient import TestClient
    from etl_enrichment_pipeline.api.main import app
    
    client = TestClient(app)
    
    def test_health_endpoint():
        """GET /health returns 200 with correct response body."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "etl-enrichment-pipeline"
        assert data["version"] == "0.1.0"
    ```
  - Create `.omo/evidence/` directory (empty, for QA output).
  - Must NOT test any agent implementation (there is none).
  - Must NOT test any API endpoints beyond /health.
  Parallelization: Wave 6 | Blocked by: 4, 5, 7, 8 | Blocks: —
  References (executor has NO interview context - be exhaustive):
  - `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Testing (lines 252-257): pytest
  - Metis finding GAP 9: sample test must verify model roundtrip + agent importability
  - Metis finding GAP 12: .omo/evidence/ directory must be created
  Acceptance criteria (agent-executable):
  ```bash
  uv run pytest -x -q tests/ --tb=short 2>&1
  ```
  Expected output: "4 passed" (or relevant count). Must exit 0.
  QA scenarios: happy — all tests pass, coverage report generated. failure — test failure, import error, missing dependencies. Evidence: .omo/evidence/task-9-project-infrastructure-setup.txt
  Commit: Y | test(infra): create tests/ directory with model, API, and importability tests

### Wave 7 — Final Lock & Verify

- [x] 10. Run final verification: lint + type-check + tests + lockfile
  What to do / Must NOT do:
  - Run all checks sequentially; ANY failure means the setup is incomplete.
  - `uv lock --check` — lockfile consistency
  - `uv run ruff check src/ tests/` — lint passes (0 errors)
  - `uv run pytest -x -q tests/ --tb=short --cov=src/etl_enrichment_pipeline --cov-report=term-missing` — all tests pass
  - `uv run python -c "import etl_enrichment_pipeline; print(f'Package OK: {etl_enrichment_pipeline.__version__}')"` — package importable
  - Record all results to `.omo/evidence/task-10-project-infrastructure-setup.txt`
  - Must NOT fix any linting issues that require design decisions (defer to next phase).
  - Must NOT add any new files during this todo.
  Parallelization: Wave 7 | Blocked by: 9 | Blocks: —
  References (executor has NO interview context - be exhaustive):
  - All previous todos
  - pyproject.toml ruff config
  - pyproject.toml pytest config
  Acceptance criteria (agent-executable):
  ```bash
  uv lock --check && uv run ruff check src/ tests/ && uv run pytest -x -q tests/ --tb=short
  ```
  All three must exit 0.
  QA scenarios: happy — 3 commands exit 0, no warnings. failure — any command fails; check specific error output. Evidence: .omo/evidence/task-10-project-infrastructure-setup.txt
  Commit: N | (verification — covered by previous commits)

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit — Verify every todo in the plan was completed. Check that all 11 agent stubs, all 3 YAML files, all Pydantic models, the API skeleton, and tests exist. Evidence: diff of `src/` and `tests/` directories against the todo list.
- [ ] F2. Code quality review — Run full lint+test gauntlet: `uv run ruff check src/ tests/ && uv run pytest -x -q tests/ --tb=short --cov=src/etl_enrichment_pipeline --cov-report=term-missing && uv lock --check`. All must pass. Evidence: `.omo/evidence/task-10-project-infrastructure-setup.txt`.
- [ ] F3. Real manual QA — Open `pyproject.toml` and verify: name is `etl-enrichment-pipeline`, requires-python is `>=3.12`, ruff select includes the configured rules, pytest testpaths includes `tests/`. Verify `.python-version` contains `3.13.14`. Verify root `extractor.py` exists and is a thin CLI shim. Verify `enrichment/` no longer exists. Evidence: output of each check.
- [ ] F4. Scope fidelity — Confirm ALL Must NOT have items: no agent implementation logic (agent stubs raise NotImplementedError), no endpoints beyond /health, no Docker/CI/CD files, no structlog config module, no CLI entry point, no database schema files. Evidence: grep for prohibited patterns.

## Commit strategy
- Branch: `feat/infrastructure-setup` created from `plan/enrichment_master_plan`
- Atomic commits per wave (5 commits total):
  1. `feat(infra): initialize uv project with pyproject.toml, .python-version, .gitignore`
  2. `feat(infra): install all project dependencies (langgraph, pydantic, fastapi, sqlglot, etc.)`
  3. `feat(infra): create src/etl_enrichment_pipeline package with all subpackages, __init__.py, and Pydantic v2 models`
  4. `feat(infra): create 11 agent stubs + RuleEngine + YAML rule files + FastAPI skeleton`
  5. `refactor(extractor): migrate extractor.py and config/ into src-layout, keep root CLI shim`
  6. `test(infra): create tests/ directory with model, API, and importability tests`
- Commit convention: conventional commits (type: feat|refactor|test|chore)
- After all commits, verify against `plan/enrichment_master_plan` that no unrelated files changed
- Do NOT merge to `main` — that is a separate decision

## Success criteria
1. `uv run python -c "import etl_enrichment_pipeline; print(etl_enrichment_pipeline.__version__)"` exits 0 and prints `0.1.0`
2. All 11 agent node functions importable from `etl_enrichment_pipeline.agents`
3. Pydantic v2 models (CanonicalSchema, PipelineState, FinalOutput) pass roundtrip serialization
4. `uv lock --check` exits 0 (lockfile is consistent)
5. `uv run ruff check src/ tests/` exits 0 (no lint errors)
6. `uv run pytest -x -q tests/` exits 0 with all tests passing
7. `GET /health` returns `200 {"status": "ok", "service": "etl-enrichment-pipeline", "version": "0.1.0"}`
8. `python extractor.py` still runs (CLI shim works)
9. Old `enrichment/` directory no longer exists
10. `connector_output.json` is in `.gitignore`
