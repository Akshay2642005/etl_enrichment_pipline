# agents-enrichment-implementation - Work Plan

## TL;DR (For humans)

**What you'll get:** 11 AI agents that read your aviation database metadata (`sqlj_son/raw_metadata.json`) and enrich it with business descriptions, role classifications, domain labels, semantic types, business entities, relationship meanings, use cases, sample SQL queries, schema patterns, and a validation report. All agents are wired into a LangGraph pipeline with a `POST /enrich` API endpoint.

**Why this approach:** The project already has all Pydantic models and YAML rules ready. This plan fills in the agent logic using LangChain + OpenAI (as you selected) and chains them through LangGraph. Every agent is implemented within the existing stub files — no new files created, no extraction work needed.

**What it will NOT do:** Connect to live databases. Perform schema extraction. Create any new files. Modify existing models or YAML rules. Require anything beyond an OpenAI API key.

**Effort:** Medium (12 todos across 4 waves)
**Risk:** Low — all agents are additive; existing tests pass throughout

**Decisions to sanity-check:** OpenAI API key must be available via `OPENAI_API_KEY`. Each agent uses `gpt-4o` with `temperature=0` for deterministic outputs. Validation is lenient (never blocks).

Your next move: approve this plan so I can write the plan file. Then you can run `$start-work` to execute it. Or request a high-accuracy Momus review first.

---

> TL;DR (machine): Medium effort, Low risk — Implement 11 enrichment agents + RuleEngine + LangGraph pipeline + API endpoint, all within existing stubs, processing sqlj_son/raw_metadata.json via LangChain OpenAI.

## Scope
### Must have
- Implement all 11 agent node functions (replace NotImplementedError stubs with real logic)
- Implement RuleEngine with YAML rule loading (PII, semantic types, patterns)
- Wire LangGraph StateGraph in `core/pipeline.py` with all agent nodes in sequence
- Add JSON adapter to convert `sqlj_son/raw_metadata.json` → CanonicalSchema
- Add `POST /enrich` API endpoint in `api/main.py`
- Install all project dependencies
- Fix `agents/__init__.py` to remove broken extraction_node import
- Tests for every agent (happy + failure paths)
- Final output matches master plan §Final Output Structure

### Must NOT have (guardrails, anti-slop, scope boundaries)
- Do NOT create `extraction_agent.py` — user explicitly declined
- Do NOT add new input files — only `sqlj_son/raw_metadata.json`
- Do NOT modify any model files (`models/`) — they are already complete
- Do NOT modify YAML rule files (`rules/*.yaml`) — they are already complete
- Do NOT connect to live databases or perform schema extraction
- Do NOT add authentication/authorization to the API
- Do NOT add background task queues or async processing — pipeline runs synchronously

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: **tests-after** + pytest (pytest-cov for code coverage)
- Evidence: .omo/evidence/task-<N>-agents-enrichment-implementation.txt

## Execution strategy
### Parallel execution waves

**Wave 1 — Foundation:** Install deps, fix __init__ import, implement RuleEngine + PatternDetection (rule-based agents, no LLM needed). These can be built and tested without API keys.

**Wave 2 — Core LLM Agents (Part 1):** Description, BusinessRole, Domain, SemanticType agents. Each requires the previous to be complete. SemanticType depends on RuleEngine.

**Wave 3 — Core LLM Agents (Part 2):** EntityDiscovery, RelationshipIntelligence, UseCase, SampleQuery agents. EntityDiscovery depends on SemanticType. Others build on entities.

**Wave 4 — Pipeline & API:** Validation agent, JSON adapter, LangGraph pipeline wiring, POST /enrich endpoint, e2e test.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1. Install deps | — | all | — |
| 2. Fix __init__ import | 1 | 4-12 | 3 |
| 3. Implement RuleEngine | 1 | 6 | 2, 4 |
| 4. Pattern Detection Agent | 1 | 11 | 2, 3 |
| 5. Description Agent | 1 | 11 | 2 |
| 6. Business Role Agent | 2 | 11 | 5 |
| 7. Domain Agent | 2 | 11 | 5 |
| 8. Semantic Type Agent | 3, 5 | 9 | 6, 7 |
| 9. Entity Discovery Agent | 8 | 10 | — |
| 10. Relationship Intelligence Agent | 9 | 12 | — |
| 11. Use Case + Sample Query Agents | 7 | 12 | 10 |
| 12. Validation Agent + Pipeline + API | 4, 10, 11 | — | — |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->
- [ ] 1. Install project dependencies from pyproject.toml
  What to do / Must NOT do: Run `uv sync` to install all declared dependencies (langchain-core, langchain-openai, langgraph, fastapi, httpx, sqlglot, simple-ddl-parser, psycopg2-binary, mysql-connector-python). Must NOT install anything outside pyproject.toml. Must NOT modify pyproject.toml.
  Parallelization: Wave 1 | Blocked by: — | Blocks: all other todos
  References: `pyproject.toml:10-24`
  Acceptance criteria: `python -c "import langchain, langgraph, fastapi, sqlglot"` succeeds without ImportError
  QA scenarios:
    - happy: Run `uv sync` — exit code 0, no errors
    - failure: N/A (package install either succeeds or fails)
  Commit: N (dependency install, not a code change)

- [ ] 2. Fix agents/__init__.py — remove broken extraction_node import
  What to do / Must NOT do: Remove the `from etl_enrichment_pipeline.agents.extraction_agent import extraction_node` line and the `"extraction_node"` string from `__all__`. Must NOT add or remove any other import. Must NOT create extraction_agent.py.
  Parallelization: Wave 1 | Blocked by: 1 | Blocks: 6, 7
  References: `src/etl_enrichment_pipeline/agents/__init__.py:13,26-27`
  Acceptance criteria: `python -c "from etl_enrichment_pipeline.agents import *"` succeeds without ImportError
  QA scenarios:
    - happy: Import works, `__all__` no longer contains "extraction_node"
    - failure: Attempt to import extraction_node raises ImportError (expected)
  Commit: Y | `fix(agents): remove broken extraction_node import from __init__.py`

- [ ] 3. Implement RuleEngine — YAML-driven rule-based classification
  What to do / Must NOT do: Fill `RuleEngine.classify()` in `agents/rule_engine.py`. Load YAML rules from `rules/pii_rules.yaml` and `rules/semantic_type_rules.yaml`. Match column_name against pattern lists (case-insensitive substring match). Return dict with `classification` and `confidence`. Also add a `classify_table_patterns()` for table-wide pattern detection. Must NOT call any LLM. Must NOT modify the YAML files.
  Parallelization: Wave 1 | Blocked by: 1 | Blocks: 8
  References:
    - `src/etl_enrichment_pipeline/agents/rule_engine.py:10-21` (current stub)
    - `src/etl_enrichment_pipeline/rules/pii_rules.yaml` (PII patterns)
    - `src/etl_enrichment_pipeline/rules/semantic_type_rules.yaml` (semantic patterns)
    - `src/etl_enrichment_pipeline/rules/__init__.py` (RULES_DIR path)
  Acceptance criteria: `pytest tests/ -k "rule_engine" -v` passes
  QA scenarios:
    - happy: `RuleEngine().classify("email", "VARCHAR")` returns `{"classification": "EMAIL", "confidence": 0.95}`
    - happy: `RuleEngine().classify("random_field", "INTEGER")` returns `{"classification": None, "confidence": 0.0}`
    - happy: Pattern matching is case-insensitive (`"EMAIL"`, `"Email"`, `"email"` all match)
  Commit: Y | `feat(agents): implement RuleEngine with YAML-based semantic/PII classification`

- [ ] 4. Implement Pattern Detection Agent — rule-based schema pattern detection
  What to do / Must NOT do: Fill `pattern_detection_node()` in `agents/pattern_detection_agent.py`. Load `rules/pattern_rules.yaml`. Scan all table columns for indicator column names. Detect: audit_trail (created_at/updated_at/created_by/updated_by), soft_delete (deleted_at/is_deleted), multi_tenancy (tenant_id/org_id), versioning (version/version_number), state_machine (status/state). Return list of detected patterns with table name, pattern name, and evidence columns. Must NOT call LLM.
  Parallelization: Wave 1 | Blocked by: 1 | Blocks: 12
  References:
    - `src/etl_enrichment_pipeline/agents/pattern_detection_agent.py:8-15` (current stub)
    - `src/etl_enrichment_pipeline/rules/pattern_rules.yaml` (pattern definitions)
    - `src/etl_enrichment_pipeline/models/pipeline_state.py:67` (PipelineState.patterns field)
    - `src/etl_enrichment_pipeline/models/agent_outputs.py:107` (PatternDetectionOutput)
  Acceptance criteria: `pytest tests/ -k "pattern_detection" -v` passes
  QA scenarios:
    - happy: Pipeline has tables with `created_at`, `updated_at`, `status` columns → detects `audit_trail` and `state_machine`
    - failure: Pipeline has no indicator columns → returns empty pattern list
    - edge: Table with `status` column but no other state columns → still detects `state_machine`
  Commit: Y | `feat(agents): implement pattern_detection_node with YAML-driven rule matching`

- [ ] 5. Implement Description Agent — LLM-based table/column description generation
  What to do / Must NOT do: Fill `description_node()` in `agents/description_agent.py`. Use `langchain_openai.ChatOpenAI` with model `gpt-4o` and `temperature=0`. For each table in canonical_schema, generate a business description (purpose, what data it stores). For each column, generate a concise description (what it represents). Use structured output parsing (`with_structured_output`) with `DescriptionOutput` model. Store results as `state.descriptions`. Must NOT modify canonical_schema or models. Must use LangChain's structured output parsing (not manual JSON parsing).
  Parallelization: Wave 2 | Blocked by: 2 | Blocks: 8
  References:
    - `src/etl_enrichment_pipeline/agents/description_agent.py:8-13` (current stub)
    - `src/etl_enrichment_pipeline/models/agent_outputs.py:27-34` (DescriptionOutput shape)
    - `src/etl_enrichment_pipeline/models/pipeline_state.py:60` (state.descriptions field)
    - `sqlj_son/raw_metadata.json` for test input schema
  Acceptance criteria: `pytest tests/ -k "description" -v` passes. With OPENAI_API_KEY set, generates real descriptions.
  QA scenarios:
    - happy: Given flight table with columns flight_id, flight_number, status → generates meaningful descriptions
    - failure: No OPENAI_API_KEY → catches APIError gracefully, returns empty descriptions with fallback
    - edge: Table with no columns → returns empty dict, no crash
  Commit: Y | `feat(agents): implement description_node with LangChain OpenAI structured output`

- [ ] 6. Implement Business Role Agent — LLM-based table role classification
  What to do / Must NOT do: Fill `business_role_node()` in `agents/business_role_agent.py`. Uses `ChatOpenAI` with structured output. Classifies each table into one of: `master_data`, `transactional`, `reference`, `audit`, `staging`, `reporting`, `fact`, `dimension`, `junction`. Uses table name, columns, and FK relationships as context. Returns dict mapping table_name → role. Stores as `state.business_roles`.
  Parallelization: Wave 2 | Blocked by: 2 | Blocks: 11
  References:
    - `src/etl_enrichment_pipeline/agents/business_role_agent.py:8-14` (current stub)
    - `src/etl_enrichment_pipeline/models/agent_outputs.py:37-44` (BusinessRoleOutput)
    - `src/etl_enrichment_pipeline/models/pipeline_state.py:61` (state.business_roles field)
    - Master plan §3. Business Role Agent for role definitions
    - `sqlj_son/raw_metadata.json` for test schema context
  Acceptance criteria: `pytest tests/ -k "business_role" -v` passes
  QA scenarios:
    - happy: `employee` table → classified as `master_data`; `attendance` → `transactional`; `employee_role` → `junction`
    - failure: LLM unavailable → empty dict, no crash
    - edge: Table with no FK references → still classified (e.g. `stand` → `reference`)
  Commit: Y | `feat(agents): implement business_role_node with LangChain OpenAI`

- [ ] 7. Implement Domain Agent — LLM-based business domain detection
  What to do / Must NOT do: Fill `domain_node()` in `agents/domain_agent.py`. Uses `ChatOpenAI` with structured output. Detects domain per table: `Logistics`, `Aviation`, `Human Resources`, `Equipment Management`, `Airport Infrastructure`, etc. Uses all table metadata as context. Returns dict mapping table_name → domain. Stores as `state.domains`.
  Parallelization: Wave 2 | Blocked by: 2 | Blocks: 11
  References:
    - `src/etl_enrichment_pipeline/agents/domain_agent.py:8-13` (current stub)
    - `src/etl_enrichment_pipeline/models/agent_outputs.py:46-53` (DomainOutput)
    - `src/etl_enrichment_pipeline/models/pipeline_state.py:62` (state.domains field)
    - Master plan §4. Domain Agent for domain examples
  Acceptance criteria: `pytest tests/ -k "domain" -v` passes
  QA scenarios:
    - happy: `flight` table → `Aviation`; `employee` table → `Human Resources`; `equipment` → `Equipment Management`
    - failure: LLM unavailable → empty dict
    - edge: Mixed-domain schema → each table gets appropriate domain
  Commit: Y | `feat(agents): implement domain_node with LangChain OpenAI`

- [ ] 8. Implement Semantic Type Agent — rule + LLM column type detection
  What to do / Must NOT do: Fill `semantic_type_node()` in `agents/semantic_type_agent.py`. First pass: use RuleEngine to classify all columns by name pattern matching (EMAIL, PHONE, FIRST_NAME, LAST_NAME, DATE_OF_BIRTH, COUNTRY, CITY, STATE, STATUS, TIMESTAMP, PII). Second pass for unclassified columns: use ChatOpenAI to infer semantic type. Return dict mapping `table_name.column_name` → semantic type. Store as `state.semantic_types`.
  Parallelization: Wave 2 | Blocked by: 3, 5 | Blocks: 9
  References:
    - `src/etl_enrichment_pipeline/agents/semantic_type_agent.py:8-14` (current stub)
    - `src/etl_enrichment_pipeline/agents/rule_engine.py` (RuleEngine for first pass)
    - `src/etl_enrichment_pipeline/models/agent_outputs.py:55-62` (SemanticTypeOutput)
    - `src/etl_enrichment_pipeline/rules/pii_rules.yaml` (PII patterns)
    - `src/etl_enrichment_pipeline/rules/semantic_type_rules.yaml` (semantic patterns)
  Acceptance criteria: `pytest tests/ -k "semantic_type" -v` passes
  QA scenarios:
    - happy: `employee.email` → `EMAIL` (rule-based); `attendance.check_in` → `TIMESTAMP` (rule-based)
    - happy: Ambiguous column like `remarks` → classified by LLM fallback
    - failure: LLM unavailable → rule-based classifications still work, LLM-only columns return None
  Commit: Y | `feat(agents): implement semantic_type_node with RuleEngine first-pass + LLM fallback`

- [ ] 9. Implement Entity Discovery Agent — LLM-based business entity extraction
  What to do / Must NOT do: Fill `entity_discovery_node()` in `agents/entity_discovery_agent.py`. Uses ChatOpenAI with structured output. Converts tables into business entity names (singular, PascalCase): `employee` → `Employee`, `attendance` → `Attendance`, `employee_role` → `EmployeeRole`. Groups related tables under entities. Returns list of entity names and optional attributes. Must NOT create duplicate entities. Stores as `state.entities`.
  Parallelization: Wave 3 | Blocked by: 8 | Blocks: 10
  References:
    - `src/etl_enrichment_pipeline/agents/entity_discovery_agent.py:8-13` (current stub)
    - `src/etl_enrichment_pipeline/models/agent_outputs.py:64-71` (EntityDiscoveryOutput)
    - `src/etl_enrichment_pipeline/models/pipeline_state.py:64` (state.entities field)
    - Master plan §6. Entity Discovery Agent for examples
  Acceptance criteria: `pytest tests/ -k "entity_discovery" -v` passes
  QA scenarios:
    - happy: `employee`, `department`, `role`, `employee_role` → entities: Employee, Department, Role (EmployeeRole is a junction, not a separate entity)
    - failure: LLM unavailable → empty list
    - edge: Single table → still produces one entity
  Commit: Y | `feat(agents): implement entity_discovery_node with LangChain OpenAI`

- [ ] 10. Implement Relationship Intelligence Agent — business relationship inference
  What to do / Must NOT do: Fill `relationship_intelligence_node()` in `agents/relationship_intelligence_agent.py`. Start with existing FK relationships from canonical_schema. Map physical (FK) relationships to entity relationships using discovered entities from state.entities. Use ChatOpenAI to generate business meaning labels: e.g. "A flight can have multiple baggage items", "An employee belongs to one department". Produce both physical_relationships (from_table, to_table) and entity_relationships (entity, related_entities, business_meaning). Stores as `state.entity_relationships`.
  Parallelization: Wave 3 | Blocked by: 9 | Blocks: 12
  References:
    - `src/etl_enrichment_pipeline/agents/relationship_intelligence_agent.py:8-14` (current stub)
    - `src/etl_enrichment_pipeline/models/agent_outputs.py:73-81` (RelationshipIntelligenceOutput)
    - `src/etl_enrichment_pipeline/models/pipeline_state.py:65` (state.entity_relationships field)
    - `src/etl_enrichment_pipeline/models/canonical.py:86-93` (RelationshipSchema with FK data)
    - Master plan §7. Relationship Intelligence Agent for output shapes
  Acceptance criteria: `pytest tests/ -k "relationship" -v` passes
  QA scenarios:
    - happy: employee→department FK → entity relationship "Employee belongs to Department"
    - happy: flight→turnaround_operation FK → entity relationship "Flight has turnaround operations"
    - failure: No FK relationships → returns empty lists
    - failure: No entities discovered → returns empty lists
  Commit: Y | `feat(agents): implement relationship_intelligence_node with FK + LLM enrichment`

- [ ] 11. Implement Use Case & Sample Query Agents — LLM-based use case + SQL generation
  What to do / Must NOT do: Fill `use_case_node()` in `agents/use_case_agent.py` and `sample_query_node()` in `agents/sample_query_agent.py`. Both use ChatOpenAI with structured output.
    - **Use Case Agent**: Generate 3-5 business use cases from the schema (e.g., "Flight Turnaround Management", "Employee Attendance Tracking", "Baggage Tracking"). Use case = dict with name, description, involved_tables.
    - **Sample Query Agent**: Generate 3-5 sample queries across categories: Lookup, Reporting, Analytics, Aggregation, Relationship. Each query = dict with question, sql, category.
    - Store in `state.use_cases` and `state.sample_queries` respectively.
  Parallelization: Wave 3 | Blocked by: 7 | Blocks: 12
  References:
    - `src/etl_enrichment_pipeline/agents/use_case_agent.py:8-13` (stub)
    - `src/etl_enrichment_pipeline/agents/sample_query_agent.py:8-15` (stub)
    - `src/etl_enrichment_pipeline/models/agent_outputs.py:83-98` (UseCaseOutput, SampleQueryOutput)
    - `src/etl_enrichment_pipeline/models/pipeline_state.py:66-68` (state fields)
    - Master plan §8-9 for examples
  Acceptance criteria: `pytest tests/ -k "use_case or sample_query" -v` passes
  QA scenarios:
    - happy: Generates meaningful use cases and SQL queries for the airport schema
    - happy: All 5 query categories represented (Lookup, Reporting, Analytics, Aggregation, Relationship)
    - failure: LLM unavailable → empty lists
  Commit: Y | `feat(agents): implement use_case_node and sample_query_node with LangChain OpenAI`

- [ ] 12. Implement Validation Agent + JSON Adapter + LangGraph Pipeline + API
  What to do / Must NOT do:
    a. **Validation Agent** (`agents/validation_agent.py`): Check for missing PKs, broken FK references, empty tables, missing descriptions, missing semantic types, low-confidence outputs. Store issues in `state.validation_report` with status PASS/WARN/FAIL. Never block pipeline.
    b. **JSON Adapter** (`core/pipeline.py`): Add `load_raw_metadata(path: str) -> CanonicalSchema` function that reads `sqlj_son/raw_metadata.json` and converts to CanonicalSchema. Map: database_type→vendor, tables[].columns→ColumnSchema (set is_primary_key from constraints), tables[].relationships→RelationshipSchema.
    c. **Pipeline wiring** (`core/pipeline.py`): Build LangGraph StateGraph with all 11 agent nodes in sequence: load_json→description→business_role→domain→semantic_type→entity_discovery→relationship→use_case→sample_query→pattern_detection→validation→assemble_final. Add `run_pipeline()` entry point.
    d. **API endpoint** (`api/main.py`): Add `POST /enrich` that accepts raw_metadata.json body, runs pipeline, returns FinalOutput JSON.
    e. **Tests** (`tests/test_api.py` and `tests/test_models.py`): Add tests for pipeline, validation, and API.
    f. Must NOT create new files. All additions go into existing stubs.
  Parallelization: Wave 4 | Blocked by: 4, 10, 11 | Blocks: —
  References:
    - `src/etl_enrichment_pipeline/agents/validation_agent.py:8-14` (stub)
    - `src/etl_enrichment_pipeline/core/pipeline.py:8-14` (stub)
    - `src/etl_enrichment_pipeline/api/main.py:8-26` (existing FastAPI app)
    - `src/etl_enrichment_pipeline/models/canonical.py:96-110` (CanonicalSchema)
    - `src/etl_enrichment_pipeline/models/final_output.py:13-30` (FinalOutput)
    - `sqlj_son/raw_metadata.json` (input format)
    - Master plan §10-11 for validation and final output structure
  Acceptance criteria:
    - `pytest tests/ -v` passes
    - `python -c "from etl_enrichment_pipeline.core.pipeline import build_pipeline; g = build_pipeline(); print(g)"` prints compiled graph
    - `python -c "from etl_enrichment_pipeline.api.main import app; print(app.routes)"` includes `/enrich`
  QA scenarios:
    - happy: Load raw_metadata.json → run pipeline → produces FinalOutput with all sections populated
    - happy: Validation finds issues → reports them in validation_report but pipeline completes
    - failure: Invalid JSON → returns validation error without crash
    - failure: Missing OPENAI_API_KEY → LLM agents return empty dicts, pipeline completes (graceful degradation)
  Commit: Y | `feat(pipeline): implement validation agent, LangGraph graph, JSON adapter, and POST /enrich`

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit — verify all 11 agents are implemented, pipeline is wired, API responds
- [ ] F2. Code quality review — ruff lint + type-check passes
- [ ] F3. Real manual QA — run pipeline against raw_metadata.json, inspect final output JSON
- [ ] F4. Scope fidelity — no extraction_agent.py created, no model files changed, no new input files

## Commit strategy
- One commit per wave. Commit messages follow conventional commits format:
  - `feat(agents): implement Wave 1 - RuleEngine, PatternDetection, foundation`
  - `feat(agents): implement Wave 2 - Description, BusinessRole, Domain, SemanticType`
  - `feat(agents): implement Wave 3 - EntityDiscovery, RelationshipIntelligence, UseCase, SampleQuery`
  - `feat(pipeline): implement Wave 4 - Validation, LangGraph pipeline, API`
- Do NOT commit before completing a full wave
- Do NOT force-push

## Success criteria
1. `pytest tests/` passes with ≥ 90% coverage on agent code
2. Pipeline processes `sqlj_son/raw_metadata.json` end-to-end without errors
3. Final output JSON contains non-empty values for: descriptions, business_roles, domains, semantic_types, entities, entity_relationships, use_cases, sample_queries, schema_patterns
4. `POST /enrich` endpoint accepts JSON and returns enriched output
5. No new files created (modifications only to existing stubs)
