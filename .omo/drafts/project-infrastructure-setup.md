---
slug: project-infrastructure-setup
status: awaiting-approval
intent: clear
pending-action: write .omo/plans/project-infrastructure-setup.md
approach: Initialize uv-managed Python project with src-layout package, Pydantic v2 models, agent stubs, YAML rules, FastAPI skeleton, test infrastructure, and all dependencies.
---

# Draft: project-infrastructure-setup

## Components (topology ledger)
| id | outcome | status | evidence path |
|---|---|---|---|
| A — uv project scaffold | pyproject.toml, .python-version, .gitignore, uv.lock, .venv | active | `docs/plan/ETL_Schema_Agent_Master_Plan.md` §Recommended Technology Stack |
| B — Package structure | src-layout `src/etl_enrichment_pipeline/` with `__init__.py` hierarchy | active | uv docs — src-layout for packaged projects; user approved |
| C — Pydantic models | CanonicalSchema, PipelineState, FinalOutput, agent-specific models | active | Master plan §Canonical Schema Model, §Final Output Structure, §LangGraph Design |
| D — Agent stubs | 11 agent `.py` files + rule_engine + pipeline orchestrator with LangGraph-compatible signatures | active | Master plan §Agent Responsibilities (agents 1-11) |
| E — Config & rules | YAML rule files (PII, patterns, semantic types); refactored config | active | Master plan §Rule Engine |
| F — Dependencies | langgraph, langchain, pydantic, fastapi, uvicorn, sqlglot, structlog, pytest, pyyaml, psycopg2, mysql-connector-python, ruff | active | Master plan §Recommended Technology Stack |
| G — API skeleton | `src/etl_enrichment_pipeline/api/main.py` with /health endpoint | active | User approved inclusion now |
| H — Test infra | `tests/` dir, conftest.py, sample test, pytest config in pyproject.toml | active | Master plan §Testing (pytest) |
| I — Developer tooling | ruff config in pyproject.toml, .gitignore | active | Modern Python standard |

## Open assumptions (announced defaults)
| assumption | adopted default | rationale | reversible? |
|---|---|---|---|
| Build backend | uv_build | uv standard for --package --lib init | Yes (pyproject.toml) |
| Python version | >=3.12 (pin 3.13) | Master plan says 3.12+, we have 3.13.14 | Yes |
| Linting tool | ruff | Modern Python standard, uv-native | Yes (pyproject.toml config) |
| YAML parser | PyYAML | Industry standard | Yes (import swap) |
| HTTP server | uvicorn | Standard for FastAPI | Yes |

## Findings (cited - path:lines)
- Python 3.13.14 is available; uv 0.9.9 is installed
- Existing project files: `extractor.py`, `config/__init__.py`, `config_global.py`, `config_postgres.py`, `config_mysql.py`
- Empty `enrichment/` directory exists for future agents
- No `.gitignore`, no `pyproject.toml`, no `requirements.txt`
- Git branch: `plan/enrichment_master_plan` (ahead of main with plan changes)
- Master plan defines 11 agents + rule engine + shared PipelineState (§LangGraph Design) + Canonical Schema Model
- Master plan defines Final Output JSON structure (§Final Output Structure)

## Decisions (with rationale)
1. **src-layout** (`src/etl_enrichment_pipeline/`) — User chose this. Clean package isolation, distribution-ready, uv standard.
2. **Package name** `etl_enrichment_pipeline` — User chose to fix the typo but stay close to the original repo name.
3. **FastAPI skeleton included now** — User approved. Minimal `/health` endpoint only, saves structural rework in Phase 5.
4. **ruff for linting** — Standard. Configured in pyproject.toml's `[tool.ruff]` section.
5. **uv_build backend** — uv default for packaged projects.

## Scope IN
- uv init with --package --lib (src-layout)
- All pyproject.toml metadata and config
- `src/etl_enrichment_pipeline/` package with models/, agents/, api/, rules/, config/ subpackages
- Pydantic v2 models: CanonicalSchema, PipelineState, FinalOutput, agent output types
- Agent stubs: 11 agent files with LangGraph node-compatible function signatures + docstrings
- Rule engine stub + YAML rule files (PII, semantic types, patterns)
- FastAPI skeleton: main.py with /health endpoint
- All deps installed via `uv add`
- tests/ directory with conftest.py + sample test
- ruff config in pyproject.toml
- .gitignore for Python artifacts
- Refactor existing extractor.py and config/ into the new package structure

## Scope OUT (Must NOT have)
- Any agent implementation logic (LLM calls, prompts, business logic)
- Any LangGraph workflow wiring beyond stub function signatures
- Any YAML rule content beyond skeleton/example files
- Any database schema or migrations (PostgreSQL is future)
- Any CI/CD pipeline
- Any Docker configuration
- Any real API endpoints beyond /health
- Any existing code deletion — only migration/refactoring

## Approval gate
status: approved
<!-- The user approved the brief. Proceeding to write the plan. -->
