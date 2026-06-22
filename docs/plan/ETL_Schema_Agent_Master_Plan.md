# ETL Schema Intelligence Agent — Final Revised Architecture (v3)

## Vision

Build an AI-powered Schema Intelligence Platform that converts:

* SQL DDL files
* Database metadata JSON files
* Multiple database schema exports

into a rich, business-aware, AI-ready JSON representation.

The platform should:

* Support multiple database vendors
* Produce a unified schema representation
* Enrich schemas with business context
* Generate entity relationships
* Generate sample SQL queries
* Detect patterns and compliance issues
* Support future agent expansion

---

# Core Architecture

```text
INPUT
│
├── SQL DDL
├── Metadata JSON
├── Multiple Database Schemas
│
▼

Schema Extraction Agent
(Rule-Based Extraction)

▼

Canonical Schema Model

▼

Description Agent

▼

Business Role Agent

▼

Domain Agent

▼

Semantic Type Agent

▼

Entity Discovery Agent

▼

Relationship Intelligence Agent

▼

Use Case Agent

▼

Sample Query Agent

▼

Pattern Detection Agent

▼

Validation Agent

▼

Final Intelligence JSON
```

---

# Architecture Principles

## Rule-Based Extraction

Extraction is deterministic.

Extraction does NOT use AI by default.

Use:

* sqlglot
* simple-ddl-parser
* JSON adapters

Responsibilities:

* parse DDL
* parse metadata JSON
* extract tables
* extract columns
* extract constraints
* extract views
* extract indexes
* extract triggers
* extract procedures

Output:

```text
Canonical Schema Model
```

---

## AI-Based Enrichment

AI is only responsible for:

* descriptions
* purposes
* business roles
* domains
* semantic types
* entity discovery
* use case generation
* sample query generation
* relationship reasoning
* pattern detection

---

# Recommended Technology Stack

## Language

```text
Python 3.12+
```

---

## Agent Framework

```text
LangGraph
```

Used from Phase 1 because the project is already a multi-agent workflow.

---

## LLM Framework

```text
LangChain
```

Used for:

* prompt templates
* structured outputs
* model abstraction

NOT for orchestration.

LangGraph handles orchestration.

---

## LLM Providers

```text
OpenAI GPT-5.5
Claude Sonnet
```

Optional:

```text
Ollama
DeepSeek
Qwen
Llama
```

for local deployments.

---

## SQL Extraction

```text
sqlglot
```

Primary parser.

Fallback:

```text
simple-ddl-parser
```

---

## Data Models

```text
Pydantic v2
```

Used for:

* Canonical Schema
* Agent State
* Final Output

---

## API Layer

```text
FastAPI
```

---

## Configuration

```text
YAML
```

Stores:

* semantic rules
* PII rules
* pattern rules
* domain rules

---

## Testing

```text
pytest
```

---

## Logging

```text
structlog
```

---

## Future Storage

```text
PostgreSQL
```

Store:

* schemas
* enrichment outputs
* agent runs
* schema versions

---

# LangGraph Design

## Shared State

All agents operate on the same state.

```python
PipelineState
```

Contains:

```python
raw_input

canonical_schema

descriptions

business_roles

domains

semantic_types

entities

entity_relationships

use_cases

sample_queries

patterns

validation_report

final_output
```

---

# Agent Responsibilities

## 1. Schema Extraction Agent

### Input

SQL DDL or metadata JSON.

### Responsibilities

Extract:

* tables
* columns
* constraints
* indexes
* views
* procedures
* triggers
* relationships

### Output

Canonical Schema Model.

### AI Usage

None.

Uses:

```text
sqlglot
simple-ddl-parser
JSON adapters
```

---

## 2. Description Agent

Generates:

```json
{
  "description": "",
  "description_confidence": 0.95
}
```

For:

* tables
* columns
* views

---

## 3. Business Role Agent

Classifies tables as:

```text
master_data
transactional
reference
audit
staging
reporting
fact
dimension
junction
```

Example:

```json
{
  "business_role": "master_data",
  "confidence": 0.92
}
```

---

## 4. Domain Agent

Detects:

```text
Healthcare
Banking
Retail
Insurance
Education
Logistics
Telecom
Manufacturing
```

Output:

```json
{
  "domain": "Healthcare",
  "confidence": 0.93
}
```

---

## 5. Semantic Type Agent

Detects business meaning of columns.

Examples:

```text
EMAIL
PHONE
ADDRESS
FIRST_NAME
LAST_NAME
FULL_NAME

PATIENT_ID
CUSTOMER_ID
ORDER_ID
ACCOUNT_ID

PRICE
AMOUNT
QUANTITY

DATE_OF_BIRTH

STATUS

TIMESTAMP

COUNTRY
CITY
STATE
```

Output:

```json
{
  "semantic_type": "EMAIL",
  "confidence": 0.97
}
```

---

## 6. Entity Discovery Agent

Converts schema objects into business entities.

Example:

```text
patients
appointments
doctors
```

Produces:

```json
{
  "entities": [
    "Patient",
    "Appointment",
    "Doctor"
  ]
}
```

---

## 7. Relationship Intelligence Agent

Produces:

### Physical Relationships

```json
{
  "from_table": "appointments",
  "to_table": "patients"
}
```

### Entity Relationships

```json
{
  "entity": "Patient",
  "related_entities": [
    "Appointment",
    "Doctor"
  ]
}
```

### Business Meaning

```json
{
  "relationship":
    "A patient can have multiple appointments"
}
```

---

## 8. Use Case Agent

Generates:

```json
{
  "use_case":
    "Appointment Scheduling"
}
```

Examples:

```text
Patient Search
Order Tracking
Inventory Management
Payment Processing
Customer Analytics
```

---

## 9. Sample Query Agent

Generates sample business queries.

Example:

```json
{
  "question":
    "Find all appointments for a patient",

  "sql":
    "SELECT * FROM appointments WHERE patient_id = ?"
}
```

Categories:

* Lookup
* Reporting
* Analytics
* Aggregation
* Relationship Queries

---

## 10. Pattern Detection Agent

Detects:

```text
audit_trail
soft_delete
multi_tenancy
versioning
state_machine
event_sourcing
```

---

## 11. Validation Agent

Validates:

### Extraction

* Missing PKs
* Broken FKs
* Empty tables

### Enrichment

* Missing descriptions
* Missing semantic types
* Low-confidence outputs

### Relationships

* Duplicate entities
* Invalid mappings

Produces:

```json
{
  "status": "PASS",
  "issues": []
}
```

---

# Rule Engine

Not all intelligence should use AI.

Use YAML-driven rules for:

## PII Detection

```yaml
pii_columns:
  - email
  - phone
  - mobile
  - aadhaar
  - pan
  - passport
```

Output:

```json
{
  "classification": "PII"
}
```

---

## Audit Pattern Detection

```text
created_at
updated_at
created_by
updated_by
```

---

## Soft Delete Detection

```text
deleted_at
is_deleted
```

---

## Common Semantic Types

```text
email
phone
mobile
dob
country
city
state
```

Can be detected without LLM calls.

---

# Confidence Policy

Only inferred values receive confidence scores.

Examples:

### Has Confidence

```json
{
  "description": "...",
  "confidence": 0.93
}
```

```json
{
  "domain": "Healthcare",
  "confidence": 0.88
}
```

```json
{
  "semantic_type": "EMAIL",
  "confidence": 0.97
}
```

---

### No Confidence

```json
{
  "table_name": "patients"
}
```

```json
{
  "column_name": "patient_id"
}
```

```json
{
  "data_type": "INTEGER"
}
```

```json
{
  "constraint_type": "PRIMARY_KEY"
}
```

Because they originate from extraction.

---

# Canonical Schema Model

Acts as the contract between extraction and enrichment.

```json
{
  "database_info": {},
  "tables": [],
  "views": [],
  "indexes": [],
  "functions": [],
  "procedures": [],
  "triggers": [],
  "relationships": []
}
```

Every source must first become this structure.

---

# Final Output Structure

```json
{
  "metadata": {},

  "tables": [],

  "views": [],

  "relationships": [],

  "entities": [],

  "entity_relationships": [],

  "business_processes": [],

  "use_cases": [],

  "sample_queries": [],

  "schema_patterns": [],

  "validation_report": []
}
```

---

# Implementation Phases

## Phase 1

Build:

* LangGraph workflow
* Schema Extraction Agent
* Canonical Schema Model
* Shared State

---

## Phase 2

Build:

* Description Agent
* Business Role Agent
* Domain Agent

---

## Phase 3

Build:

* Semantic Type Agent
* Entity Discovery Agent
* Relationship Intelligence Agent

---

## Phase 4

Build:

* Use Case Agent
* Sample Query Agent
* Pattern Detection Agent

---

## Phase 5

Build:

* Validation Agent
* Human Review Workflow
* FastAPI Service
* Multi-Schema Processing
* Plugin System

```

---

# Current Project Structure

```text
etl_enrichment_pipline/
│
├── config/                          # Database connector configurations
│   ├── __init__.py                  # Empty package init
│   ├── config_global.py             # Global pipeline settings (env, log level, output)
│   ├── config_postgres.py           # PostgreSQL database connections (3 systems)
│   └── config_mysql.py              # MySQL database connections (4 systems)
│
├── docs/
│   └── plan/
│       └── ETL_Schema_Agent_Master_Plan.md   # This file — architecture master plan
│
├── enrichment/                      # Future enrichment agents (empty, Phase 2+)
│
├── .codegraph/                      # Codebase indexing (auto-generated)
│
├── extractor.py                     # Phase 1 — Schema Extraction Agent (rule-based)
├── README.md                        # Project overview
└── connector_output.json            # Extraction output (gitignored, generated at runtime)
```

---

# MVP (Minimum Viable Product)

The **current codebase is an MVP of Phase 1** from the implementation plan above.

## What MVP Delivers

| Capability | Status |
|---|---|
| Multi-vendor schema extraction (PostgreSQL + MySQL) | ✅ Done |
| Rule-based extraction (direct SQL queries via information_schema) | ✅ Done |
| Canonical JSON output structure | ✅ Done |
| Config-driven database connections | ✅ Done |
| Extraction rules per database (toggle columns/views/relations) | ✅ Done |
| Error handling with in-JSON error logging per system | ✅ Done |
| Airline/aviation domain — 7 production-like systems | ✅ Done |

## MVP Connected Systems

| System Name | DB Type | Business Domain |
|---|---|---|
| Departure Control System (DCS) | PostgreSQL | Flight operations |
| Passenger Service System (PSS) | PostgreSQL | Passenger management |
| Revenue Management System (RMS) | PostgreSQL | Pricing & analytics |
| Maintenance Management System (MRO) | MySQL | Aircraft maintenance |
| Crew Management System | MySQL | Crew rostering |
| Loyalty Program | MySQL | Frequent flyer |
| Ground Resource System | MySQL | Ground operations |

## MVP Extraction Output Shape

```json
{
  "metadata": {
    "environment": "development",
    "status": "success"
  },
  "systems": {
    "<system_name>": {
      "database_type": "postgres|mysql",
      "columns": [
        {
          "table_name": "",
          "column_name": "",
          "data_type": "",
          "max_length": null
        }
      ],
      "views": [
        {
          "view_name": "",
          "definition": ""
        }
      ],
      "relationships": [
        {
          "source_table": "",
          "source_column": "",
          "target_table": "",
          "target_column": ""
        }
      ]
    }
  }
}
```

## What MVP Does NOT Yet Cover (Deferred to Later Phases)

| Feature | Planned Phase |
|---|---|
| LangGraph workflow orchestration | Phase 1 |
| sqlglot DDL parsing (direct SQL used instead) | Phase 1 |
| AI-based description generation | Phase 2 |
| Business role classification | Phase 2 |
| Domain detection | Phase 2 |
| Semantic type detection | Phase 3 |
| Entity discovery | Phase 3 |
| Relationship intelligence | Phase 3 |
| Use case generation | Phase 4 |
| Sample query generation | Phase 4 |
| Pattern detection | Phase 4 |
| Validation agent | Phase 5 |
| FastAPI service layer | Phase 5 |
| PostgreSQL persistent storage | Future |
| YAML rule engine (PII, patterns) | Phase 2-3 |

---

# File Structure & Responsibility Breakdown

## Root: `extractor.py`

**Role**: Schema Extraction Agent — Phase 1 MVP entry point.

**Responsibilities**:
- Iterates over all configured databases (PostgreSQL + MySQL)
- Connects using credentials from `config/` module
- Executes `information_schema` queries to extract columns, views, and foreign key relationships
- Aggregates all extracted data into a unified JSON structure
- Writes output to `connector_output.json`
- Handles per-database connection failures gracefully (logs error in JSON, continues)

**Database Handling**:
- **PostgreSQL**: queries `information_schema.columns` and `information_schema.views` (public schema)
- **MySQL**: queries `INFORMATION_SCHEMA.COLUMNS` and `INFORMATION_SCHEMA.KEY_COLUMN_USAGE` (foreign keys)
- Extraction rules toggle which queries run per database

**Planned Evolution**: Will be refactored into a LangGraph node as the first step in the pipeline. Rule-based extraction logic will be extended to use sqlglot/simple-ddl-parser for offline DDL file processing.

---

## `config/` Module

### `config_global.py`

**Role**: Global pipeline configuration.

```python
GLOBAL_PIPELINE = {
    "environment": "development",
    "log_level": "info"
}

CONNECTOR_SETTINGS = {
    "output_format": "json",
    "output_file": "connector_output.json"
}
```

**Planned Evolution**: Will grow to include schema versioning, LLM provider configs, agent timeouts, and LangGraph thread configuration.

### `config_postgres.py`

**Role**: PostgreSQL database definitions.

Contains `POSTGRES_DBS` — a list of 3 aviation-domain PostgreSQL databases:
- **Departure Control System** (dcs_prod)
- **Passenger Service System** (pss_core)
- **Revenue Management System** (rms_analytics)

Each entry defines:
- `system_name` — business identifier
- `connection_name` — internal routing key
- `db_type` — `"postgres"` for connector dispatch
- `credentials` — host, port, database, username, password
- `extraction_rules` — boolean toggles for `extract_table_info`, `extract_ddl_views`, `extract_relations`

### `config_mysql.py`

**Role**: MySQL database definitions.

Contains `MYSQL_DBS` — a list of 4 aviation-domain MySQL databases:
- **Maintenance Management System** (mro_db)
- **Crew Management System** (crew_roster_db)
- **Loyalty Program** (frequent_flyer_db)
- **Ground Resource System** (ground_ops_db)

Same structure as PostgreSQL config but MySQL-specific extraction rules (no view extraction since MySQL views are not extracted in the MVP).

### `__init__.py`

**Role**: Package marker. Empty.

---

## `enrichment/` (Directory)

**Role**: Location for all future enrichment agents (Phases 2–5).

**Current state**: Empty directory.

**Planned files**:
- `description_agent.py` — Generates table/column descriptions (LLM)
- `business_role_agent.py` — Classifies tables as master/transactional/fact/dimension etc.
- `domain_agent.py` — Detects business domain
- `semantic_type_agent.py` — Detects PII, email, phone, IDs etc.
- `entity_discovery_agent.py` — Maps tables to business entities
- `relationship_intelligence_agent.py` — Infers business relationships
- `use_case_agent.py` — Generates business use cases
- `sample_query_agent.py` — Generates sample SQL queries
- `pattern_detection_agent.py` — Detects audit trail, soft delete, multi-tenancy
- `validation_agent.py` — Validates extraction and enrichment quality
- `rule_engine.py` — YAML-driven rule-based classification (PII, semantic types)
- `pipeline.py` — LangGraph workflow definition and state management

---

## `docs/plan/`

**Role**: Architecture and planning documentation.

Contains the master plan document (`ETL_Schema_Agent_Master_Plan.md`) — the single source of truth for architecture decisions, agent definitions, implementation phases, and project structure.

---

## Root Files

| File | Role |
|---|---|
| `extractor.py` | Phase 1 MVP — rule-based schema extractor (entry point) |
| `connector_output.json` | Runtime output — extracted schema JSON (not committed) |
| `README.md` | Project overview (minimal — 1 line) |

---

## `connector_output.json` (Runtime)

**Role**: The final output of the MVP extraction phase. Consumed by Phase 2+ enrichment agents.

**Structure**: Matches the `"systems"`-keyed JSON format defined in `extractor.py`:

```json
{
  "metadata": { "environment": "...", "status": "success|partial_failure" },
  "systems": {
    "<system_name>": {
      "database_type": "postgres|mysql",
      "columns": [...],
      "views": [...],
      "relationships": [...],
      "error": "..."  // only present on connection failure
    }
  }
}
```

**Planned Evolution**: Will be replaced by the **Final Intelligence JSON** format defined in the architecture section above once all enrichment agents are implemented.
```
