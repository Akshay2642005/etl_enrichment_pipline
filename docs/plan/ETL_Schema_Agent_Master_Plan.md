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
```
