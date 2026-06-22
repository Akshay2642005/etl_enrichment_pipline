# ETL Schema Intelligence Agent — Master Plan
## AI-Native, Skills-Based Architecture for Database Schema Extraction & Enrichment

**Version:** 1.0.0  
**Date:** 2026-06-22  
**Status:** Planning Phase — Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Core Components](#3-core-components)
4. [Skill Inventory](#4-skill-inventory)
5. [Tech Stack](#5-tech-stack)
6. [File Structure](#6-file-structure)
7. [Data Flow](#7-data-flow)
8. [Output JSON Specification](#8-output-json-specification)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Risk & Mitigation](#10-risk--mitigation)
11. [Appendix](#11-appendix)

---

## 1. Executive Summary

### Vision
Build an AI-powered agent that ingests database schema definitions (JSON metadata or SQL DDL) and produces a rich, standardized, semantically-enriched JSON representation. The agent uses a skills-based architecture where each skill is an AI-capable module handling a specific phase of the pipeline.

### Key Principles
- **AI-Native:** No rule-based parsing; all extraction and enrichment powered by LLM reasoning
- **Database-Agnostic:** Handles PostgreSQL, MySQL, SQL Server, Oracle, SQLite, and any future dialect via generalization
- **Reusable:** Modular skills can be composed, extended, and reused across projects
- **Self-Assessing:** Every inference carries a confidence score
- **Extensible:** Plugin architecture for new skills, dialects, and output formats

### Target Users
- Data engineers building ETL pipelines
- Data architects documenting legacy systems
- Teams migrating between database platforms
- AI systems needing structured schema understanding

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────────┐  │
│  │  JSON File  │    │  SQL File   │    │  Mixed / Directory / API        │  │
│  │  (.json)    │    │  (.sql)     │    │  (multiple sources)               │  │
│  └──────┬──────┘    └──────┬──────┘    └─────────────────────────────────┘  │
│         └───────────────────┬─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI AGENT ORCHESTRATOR                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Reasoning Engine: Plans, delegates, chains skills, manages state    │    │
│  │  - Detects input format & dialect                                  │    │
│  │  - Selects skill pipeline based on context                         │    │
│  │  - Handles multi-turn refinement & clarification                   │    │
│  │  - Aggregates confidence scores & generates final output            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
┌────────────────────┐      ┌────────────────────┐      ┌────────────────────┐
│    SKILL 1         │      │    SKILL 2         │      │    SKILL 3         │
│  Schema Extractor  │      │  Semantic Enricher │      │  Quality Validator │
│  (Parsing)         │      │  (Inference)       │      │  (Assurance)       │
└────────┬───────────┘      └────────┬───────────┘      └────────┬───────────┘
         │                           │                           │
         │         ┌─────────────────┘                           │
         │         │                                               │
         │         ▼                                               │
         │  ┌────────────────────┐                                 │
         │  │  SKILL 2b          │                                 │
         │  │  Schema Intelligence │                                 │
         │  │  (Pattern Detection) │                                 │
         │  └────────────────────┘                                 │
         │                                                       │
         └─────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT GENERATOR                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Serializes enriched schema to standardized JSON                     │   │
│  │  Includes: metadata, confidence scores, AI insights, suggestions       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Components

### 3.1 Agent Orchestrator

The central brain of the system. Not just a router — it reasons about the task, plans the skill execution order, and manages state across the pipeline.

**Responsibilities:**
- **Input Analysis:** Detect format (JSON vs SQL), encoding, size, complexity
- **Dialect Detection:** Identify database vendor from SQL content (not file extension)
- **Pipeline Planning:** Determine which skills to invoke and in what order
- **Context Management:** Maintain conversation state for multi-turn processing
- **Error Recovery:** Retry with different strategies if a skill fails
- **Confidence Aggregation:** Compute overall pipeline confidence from skill scores
- **Output Assembly:** Merge all skill outputs into final JSON

**Key Behaviors:**
```
1. RECEIVE input file(s)
2. ANALYZE content → determine format + dialect
3. PLAN skill pipeline:
   IF format == JSON:
      → extract_json_schema → enrich_metadata → validate
   IF format == SQL:
      → detect_dialect → extract_sql_ddl → enrich_metadata → validate
4. EXECUTE skills sequentially, passing intermediate state
5. CHECK confidence thresholds:
   IF any skill < 0.7 confidence → trigger clarification or retry
6. ASSEMBLE final output with all metadata + confidence scores
7. RETURN standardized JSON
```

### 3.2 State Manager

Maintains the working schema object throughout the pipeline. All skills read from and write to this shared state.

```python
class PipelineState:
    - raw_input: str              # Original file content
    - detected_format: str      # "json" | "sql"
    - detected_dialect: str     # "postgresql" | "mysql" | "oracle" | ...
    - intermediate_schema: SchemaObject  # Unified model
    - enrichment_results: dict  # Skill 2 outputs
    - validation_report: dict   # Skill 3 outputs
    - confidence_scores: dict   # Per-field confidence
    - final_output: dict        # Generated JSON
```

---

## 4. Skill Inventory

### 4.1 Skill 1: Schema Extractor

**Purpose:** Convert raw input (JSON or SQL) into a unified, structured schema representation.

#### Sub-Skill 1.1: `extract_json_schema`

| Attribute | Value |
|-----------|-------|
| **Input** | JSON file content (various vendor formats) |
| **Output** | Normalized `SchemaObject` (intermediate model) |
| **AI Role** | Understands varying JSON structures from different tools (pg_dump, mysqldump, information_schema, custom exports) and normalizes them |

**Handling Variations:**
- PostgreSQL `information_schema` JSON vs MySQL `SHOW CREATE TABLE` JSON vs custom tool exports
- Different key naming conventions (`column_name` vs `colName` vs `field`)
- Nested vs flat structures
- Missing optional fields (graceful degradation)

**Example Input Variations Handled:**
```json
// PostgreSQL information_schema style
{"table_name": "orders", "column_name": "order_id", "data_type": "integer"}

// MySQL SHOW style
{"Table": "orders", "Field": "order_id", "Type": "int(11)"}

// Custom tool export
{"name": "orders", "columns": [{"name": "order_id", "type": "INT"}]}
```

#### Sub-Skill 1.2: `extract_sql_ddl`

| Attribute | Value |
|-----------|-------|
| **Input** | SQL DDL file/string (CREATE TABLE, ALTER TABLE, CREATE INDEX, CREATE VIEW, etc.) |
| **Output** | Parsed `SchemaObject` with tables, columns, constraints, indexes, views |
| **AI Role** | LLM reads SQL like a senior DBA — understands context, vendor syntax, implied constraints, and semantic intent |

**Why LLM over Traditional Parser:**
- Handles messy, commented, or non-standard DDL that breaks grammar parsers
- Understands implied constraints (`id INT` in context often means PRIMARY KEY)
- Parses vendor-specific syntax by analogy even if never explicitly trained
- Extracts semantic intent from constraint names (`fk_orders_customer` → links to customers)
- Handles multi-statement files, stored procedures, triggers (skips non-DDL intelligently)

**Example Reasoning:**
```sql
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL,
    total DECIMAL(10,2) DEFAULT 0.00,
    status VARCHAR(20) CHECK (status IN ('pending', 'shipped', 'delivered')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
→ Agent infers:
- `order_id` is identity/primary key
- `customer_id` likely has FK (even if not declared here — may be in ALTER TABLE later)
- `status` has business logic embedded (state machine)
- `created_at` is audit timestamp
- Table is transactional (has status, timestamps, monetary field)

#### Sub-Skill 1.3: `detect_dialect`

| Attribute | Value |
|-----------|-------|
| **Input** | SQL content string |
| **Output** | Database type + version confidence scores |
| **AI Role** | Pattern recognition across dialects using keyword heuristics + LLM reasoning |

**Detection Signals:**
| Signal | Dialect |
|--------|---------|
| `ENGINE=InnoDB`, `AUTO_INCREMENT`, `VARCHAR` without length check | MySQL |
| `SERIAL`, `TEXT[]`, `JSONB`, `UUID`, `GENERATED ALWAYS` | PostgreSQL |
| `NVARCHAR`, `IDENTITY(1,1)`, `DATETIME2`, `GO` batch separator | SQL Server |
| `NUMBER`, `VARCHAR2`, `CLOB`, `PL/SQL` blocks | Oracle |
| `AUTOINCREMENT`, `INTEGER PRIMARY KEY` shorthand | SQLite |
| `CREATE TABLESPACE`, `DB2` specific types | DB2 |

### 4.2 Skill 2: Semantic Enricher

**Purpose:** Add business meaning, descriptions, and domain context to raw schema objects.

#### Sub-Skill 2.1: `infer_descriptions`

| Attribute | Value |
|-----------|-------|
| **Input** | Table names, column names, constraint names, view definitions |
| **Output** | Human-readable descriptions + confidence scores |
| **AI Role** | Naming convention analysis + domain context + semantic reasoning |

**Examples:**
```
Input:  table="cust_addr", columns=["cust_id", "addr_line1", "zip_cd"]
Output: description="Customer shipping and billing addresses"
        confidence=0.94

Input:  column="created_at"
Output: description="Timestamp when the record was created"
        confidence=0.99
        detected_pattern="audit_timestamp"

Input:  column="email_verified"
Output: description="Flag indicating whether the customer's email address has been verified"
        confidence=0.91
        business_meaning="Trust/signal for account security and communication eligibility"
```

#### Sub-Skill 2.2: `classify_business_role`

| Attribute | Value |
|-----------|-------|
| **Input** | Table structure, relationships, column types, naming patterns |
| **Output** | Business role classification + confidence |
| **AI Role** | Pattern matching + domain reasoning + schema topology analysis |

**Classification Taxonomy:**
| Role | Characteristics |
|------|----------------|
| `transactional` | High write volume, timestamps, status fields, FKs to master data |
| `master_data` | Slowly changing, referenced by many tables, descriptive fields |
| `reference` | Static data, lookup values, code tables, small row count |
| `staging` | Temporary, ETL prefixes, no indexes, bulk load patterns |
| `audit` | Log tables, append-only, timestamps, user tracking |
| `bridge/junction` | Composite PKs, only FK columns, many-to-many resolution |
| `reporting` | Denormalized, aggregations, materialized views |

**Example:**
```
Table: "orders"
- Has status field (pending/shipped/delivered)
- Has created_at, updated_at
- Has FK to customers
- Has monetary fields (total, tax)
- Referenced by order_items
→ Classification: transactional (confidence: 0.96)
```

#### Sub-Skill 2.3: `identify_key_processes`

| Attribute | Value |
|-----------|-------|
| **Input** | Table name + schema topology + business role |
| **Output** | List of business processes this table participates in |
| **AI Role** | Maps schema structure to business workflows |

**Example:**
```
Table: "orders"
- Order placement (high confidence: 0.98)
- Order fulfillment (high confidence: 0.94)
- Revenue recognition (medium confidence: 0.72)
- Customer analytics (medium confidence: 0.68)
```

#### Sub-Skill 2.4: `infer_purpose`

| Attribute | Value |
|-----------|-------|
| **Input** | Full table context within schema |
| **Output** | Concise "why this exists" statement |
| **AI Role** | Holistic schema reasoning — understands table's role in the bigger picture |

**Example:**
```
Table: "order_items"
- Child of "orders" (FK + composite PK)
- Contains product references + quantities + prices
- No independent existence
→ Purpose: "Captures line-item level details for each order, enabling product-level 
            revenue tracking and inventory allocation"
```

#### Sub-Skill 2.5: `extract_domain`

| Attribute | Value |
|-----------|-------|
| **Input** | All table names, column patterns, data types across schema |
| **Output** | Domain classification + secondary domains |
| **AI Role** | Cross-schema pattern recognition |

**Example:**
```
Detected patterns:
- Tables: customers, orders, order_items, products, inventory, payments
- Columns: email, shipping_address, credit_card_token, product_sku
- Domain: e-commerce (confidence: 0.93)
- Secondary: inventory_management, payment_processing, customer_relationship
```

### 4.3 Skill 3: Schema Intelligence

**Purpose:** Detect patterns, relationships, and implicit structures across the entire schema.

#### Sub-Skill 3.1: `map_relationships`

| Attribute | Value |
|-----------|-------|
| **Input** | All tables + explicit FKs + naming patterns |
| **Output** | Complete relationship graph with cardinality + business meaning |
| **AI Role** | Resolves implied relationships even without explicit FKs |

**Example:**
```
Explicit: orders.customer_id → customers.customer_id (FK declared)
Inferred: order_items.product_id → products.product_id (no FK, but naming + type match)
Inferred: orders.user_id → users.id (different naming convention, but semantic match)
```

#### Sub-Skill 3.2: `detect_patterns`

| Attribute | Value |
|-----------|-------|
| **Input** | Column naming across all tables |
| **Output** | Design patterns detected + affected tables/columns |
| **AI Role** | Recognizes recurring architectural patterns |

**Detectable Patterns:**
| Pattern | Signature | Example Tables |
|---------|-----------|----------------|
| `audit_trail` | `created_at`, `updated_at`, `created_by`, `updated_by` | orders, customers, products |
| `soft_delete` | `deleted_at`, `is_deleted`, `deleted_by` | customers, products |
| `multi_tenancy` | `tenant_id`, `org_id` on every table | all tables |
| `versioning` | `version`, `effective_date`, `expiry_date` | pricing, contracts |
| `state_machine` | `status` with CHECK constraint or enum | orders, payments, shipments |
| `event_sourcing` | `event_type`, `aggregate_id`, `sequence_number` | events table |
| `CQRS` | Separate read/write tables with similar names | orders vs order_summaries |

#### Sub-Skill 3.3: `infer_constraints`

| Attribute | Value |
|-----------|-------|
| **Input** | Column names + types + sample data (if available) |
| **Output** | Likely constraints that should exist but aren't declared |
| **AI Role** | Semantic + statistical reasoning |

**Example:**
```
Column: "email" VARCHAR(255) — no UNIQUE declared
→ Inferred: likely UNIQUE (confidence: 0.89)
   Reason: email is standardly unique per user

Column: "price" DECIMAL(10,2) — no CHECK declared
→ Inferred: likely CHECK (price >= 0) (confidence: 0.92)
   Reason: prices are non-negative in business context
```

### 4.4 Skill 4: Quality Validator

**Purpose:** Ensure output completeness, consistency, and accuracy.

#### Sub-Skill 4.1: `validate_schema`

| Attribute | Value |
|-----------|-------|
| **Input** | Generated JSON + original source |
| **Output** | Consistency report with issues and severity |
| **AI Role** | Checks for logical inconsistencies a human DBA would catch |

**Validation Checks:**
- Orphaned foreign keys (references non-existent table/column)
- Duplicate names within scope
- Missing descriptions on critical tables
- Type mismatches in relationships
- Circular dependencies
- Tables with no columns
- Views referencing non-existent tables

#### Sub-Skill 4.2: `confidence_scoring`

| Attribute | Value |
|-----------|-------|
| **Input** | Any inferred field from enrichment skills |
| **Output** | 0-1 confidence score + reasoning |
| **AI Role** | Self-assessment of its own inferences |

**Scoring Factors:**
- Naming clarity (unambiguous vs cryptic)
- Context availability (related tables, constraints, comments)
- Pattern match strength (how well it fits known patterns)
- Domain familiarity (how well-known the domain is)

#### Sub-Skill 4.3: `suggest_improvements`

| Attribute | Value |
|-----------|-------|
| **Input** | Current output + validation results |
| **Output** | Actionable suggestions for gaps or improvements |
| **AI Role** | Proactive identification of missing metadata |

**Example Suggestions:**
```
- "Table 'xref_product_category' has no description — likely a junction table 
   for products and categories. Consider adding business purpose."
- "Column 'metadata' in table 'events' is JSON type — consider documenting 
   expected schema for this field."
- "No indexes detected on 'orders.status' — frequent filtering likely, 
   consider adding index."
- "Table 'legacy_imports' appears to be staging data — consider documenting 
   retention policy."
```

---

## 5. Tech Stack

### 5.1 Core Framework

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Agent Framework** | LangChain / LangGraph | Native support for skills (tools), state management, multi-turn reasoning, and chaining |
| **LLM Backend** | OpenAI GPT-4o / Claude 3.5 Sonnet / Local LLM (Ollama) | GPT-4o for production (best SQL understanding); Claude for reasoning; local for privacy |
| **State Management** | LangGraph StateGraph | Persistent state across skill invocations, checkpointing, human-in-the-loop |
| **Orchestration** | Custom Orchestrator built on LangGraph | Fine-grained control over skill routing, retry logic, confidence thresholds |

### 5.2 Data & Models

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Schema Models** | Pydantic v2 | Type-safe, validation, JSON serialization, IDE support |
| **Intermediate Representation** | Pydantic Models | Strong typing for tables, columns, constraints, relationships |
| **Type Registry** | Python Enum + Mapping Dict | Database-agnostic type standardization |
| **JSON Output** | Pydantic `model_dump_json()` | Consistent, validated output generation |

### 5.3 Input Processing

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **File I/O** | Python `pathlib` + `aiofiles` | Async file reading, encoding detection |
| **Encoding Detection** | `chardet` | Auto-detect file encoding (UTF-8, UTF-16, etc.) |
| **Large File Handling** | Streaming + Chunking | Process SQL files > 100MB by splitting statements |
| **SQL Statement Splitting** | Custom splitter (regex + LLM validation) | Handle complex statements, preserve comments |

### 5.4 AI/ML Infrastructure

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Prompt Management** | LangChain Prompt Templates | Versioned, testable, reusable prompts per skill |
| **Few-Shot Examples** | JSON/YAML example banks | In-context learning for each skill |
| **Output Parsing** | LangChain Output Parsers | Structured output (JSON mode, function calling) |
| **Embedding Cache** | ChromaDB / FAISS | Cache schema embeddings for similarity search across schemas |
| **Model Routing** | LiteLLM | Unified interface to multiple LLM providers |

### 5.5 Testing & Quality

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Unit Testing** | `pytest` | Standard Python testing |
| **Integration Testing** | `pytest` + test fixtures | Test full pipeline with sample schemas |
| **LLM Evaluation** | `promptfoo` / custom eval framework | Measure extraction accuracy, description quality |
| **Regression Testing** | Golden dataset | Compare outputs against known-good schemas |
| **Property Testing** | `hypothesis` | Generate random valid/invalid inputs |

### 5.6 Deployment & Operations

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Packaging** | Python `hatch` / `poetry` | Modern dependency management |
| **Containerization** | Docker | Reproducible environments |
| **API Server** | FastAPI (optional) | REST API for agent as a service |
| **CLI** | `typer` | User-friendly command-line interface |
| **Logging** | `structlog` | Structured JSON logging |
| **Monitoring** | `prometheus_client` + Grafana | Track confidence scores, latency, error rates |
| **Configuration** | `pydantic-settings` + `.env` | Environment-based configuration |

### 5.7 Optional Enhancements

| Component | Technology | Use Case |
|-----------|-----------|----------|
| **Vector DB** | Pinecone / Weaviate | Semantic search across schema history |
| **Graph DB** | Neo4j | Store and query relationship graphs |
| **Cache** | Redis | Cache LLM responses for repeated schemas |
| **Workflow** | Temporal / Prefect | Long-running schema processing jobs |

---

## 6. File Structure

```
etl-schema-agent/
│
├── pyproject.toml                      # Project metadata, dependencies, build config
├── README.md                           # Project overview and quickstart
├── LICENSE
├── .env.example                        # Template for environment variables
├── .gitignore
│
├── src/
│   └── etl_schema_agent/
│       │
│       ├── __init__.py                 # Package version, exports
│       ├── main.py                     # CLI entry point, FastAPI app (optional)
│       │
│       ├── core/                       # Core framework — orchestrator, state, config
│       │   ├── __init__.py
│       │   ├── orchestrator.py         # AgentOrchestrator: plans, delegates, manages state
│       │   ├── state.py                # PipelineState: shared state across skills
│       │   ├── config.py               # Pydantic-settings: LLM keys, thresholds, paths
│       │   ├── exceptions.py           # Custom exceptions (SkillError, ValidationError, etc.)
│       │   └── logger.py               # Structured logging setup
│       │
│       ├── models/                     # Pydantic data models — the shared language
│       │   ├── __init__.py
│       │   ├── schema.py               # Core schema objects: Schema, Table, Column, etc.
│       │   ├── constraints.py          # Constraint models: PK, FK, Unique, Check, etc.
│       │   ├── relationships.py        # Relationship graph models
│       │   ├── types.py                # Data type models: NativeType, StandardizedType
│       │   ├── enrichment.py           # Enrichment result models: Description, BusinessRole, etc.
│       │   ├── validation.py           # Validation report models
│       │   └── output.py               # Final output JSON model (matches your spec)
│       │
│       ├── skills/                     # Skill implementations — each is a self-contained AI module
│       │   ├── __init__.py
│       │   ├── base.py                 # BaseSkill: abstract class all skills inherit
│       │   │
│       │   ├── extraction/             # Skill 1: Schema Extraction
│       │   │   ├── __init__.py
│       │   │   ├── extract_json.py     # Sub-skill 1.1: Parse JSON metadata
│       │   │   ├── extract_sql.py      # Sub-skill 1.2: Parse SQL DDL (LLM-based)
│       │   │   ├── detect_dialect.py   # Sub-skill 1.3: Detect DB dialect
│       │   │   └── prompts/            # LLM prompts for extraction
│       │   │       ├── extract_json.txt
│       │   │       ├── extract_sql.txt
│       │   │       └── detect_dialect.txt
│       │   │
│       │   ├── enrichment/             # Skill 2: Semantic Enrichment
│       │   │   ├── __init__.py
│       │   │   ├── infer_descriptions.py      # Sub-skill 2.1
│       │   │   ├── classify_business_role.py  # Sub-skill 2.2
│       │   │   ├── identify_processes.py      # Sub-skill 2.3
│       │   │   ├── infer_purpose.py           # Sub-skill 2.4
│       │   │   ├── extract_domain.py          # Sub-skill 2.5
│       │   │   └── prompts/
│       │   │       ├── infer_descriptions.txt
│       │   │       ├── classify_business_role.txt
│       │   │       ├── identify_processes.txt
│       │   │       ├── infer_purpose.txt
│       │   │       └── extract_domain.txt
│       │   │
│       │   ├── intelligence/           # Skill 3: Schema Intelligence
│       │   │   ├── __init__.py
│       │   │   ├── map_relationships.py       # Sub-skill 3.1
│       │   │   ├── detect_patterns.py         # Sub-skill 3.2
│       │   │   ├── infer_constraints.py       # Sub-skill 3.3
│       │   │   └── prompts/
│       │   │       ├── map_relationships.txt
│       │   │       ├── detect_patterns.txt
│       │   │       └── infer_constraints.txt
│       │   │
│       │   └── validation/             # Skill 4: Quality Validation
│       │       ├── __init__.py
│       │       ├── validate_schema.py         # Sub-skill 4.1
│       │       ├── confidence_scoring.py      # Sub-skill 4.2
│       │       ├── suggest_improvements.py    # Sub-skill 4.3
│       │       └── prompts/
│       │           ├── validate_schema.txt
│       │           ├── confidence_scoring.txt
│       │           └── suggest_improvements.txt
│       │
│       ├── utils/                      # Shared utilities
│       │   ├── __init__.py
│       │   ├── file_utils.py           # File reading, encoding detection, streaming
│       │   ├── sql_utils.py            # SQL statement splitting, comment extraction
│       │   ├── json_utils.py           # JSON normalization, schema detection
│       │   ├── type_mapping.py         # DB-type → Standardized type registry
│       │   └── embedding_utils.py      # Embedding generation, similarity search
│       │
│       ├── plugins/                    # Extensibility — drop-in dialects/skills
│       │   ├── __init__.py
│       │   ├── base_plugin.py          # Plugin interface
│       │   ├── dialects/               # Additional database dialects
│       │   │   ├── __init__.py
│       │   │   ├── db2.py
│       │   │   ├── snowflake.py
│       │   │   └── bigquery.py
│       │   └── custom_skills/          # User-defined skills
│       │       ├── __init__.py
│       │       └── example_skill.py
│       │
│       └── api/                        # Optional REST API layer
│           ├── __init__.py
│           ├── router.py               # FastAPI routes
│           ├── schemas.py              # API request/response models
│           └── dependencies.py         # DI: LLM client, state manager
│
├── tests/                              # Test suite
│   ├── __init__.py
│   ├── conftest.py                     # pytest fixtures, shared test config
│   ├── unit/                           # Unit tests per component
│   │   ├── test_models.py
│   │   ├── test_extraction.py
│   │   ├── test_enrichment.py
│   │   └── test_validation.py
│   ├── integration/                    # Full pipeline tests
│   │   ├── test_postgresql_schema.py
│   │   ├── test_mysql_schema.py
│   │   ├── test_oracle_schema.py
│   │   └── test_json_input.py
│   ├── fixtures/                       # Test data
│   │   ├── schemas/
│   │   │   ├── postgresql/
│   │   │   │   ├── ecommerce.sql
│   │   │   │   └── healthcare.sql
│   │   │   ├── mysql/
│   │   │   │   ├── ecommerce.sql
│   │   │   │   └── social_media.sql
│   │   │   ├── oracle/
│   │   │   │   └── finance.sql
│   │   │   └── json/
│   │   │       ├── pg_info_schema.json
│   │   │       └── custom_export.json
│   │   └── expected_outputs/           # Golden outputs for regression testing
│   │       ├── ecommerce_expected.json
│   │       └── healthcare_expected.json
│   └── e2e/                            # End-to-end CLI tests
│       └── test_cli.py
│
├── docs/                               # Documentation
│   ├── architecture.md
│   ├── skill_development_guide.md
│   ├── api_reference.md
│   └── examples/
│       ├── postgresql_example.md
│       ├── mysql_example.md
│       └── json_example.md
│
├── scripts/                            # Dev/ops scripts
│   ├── setup.sh
│   ├── run_tests.sh
│   └── benchmark.py                    # Performance benchmarking
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── .github/
    └── workflows/
        ├── ci.yml                      # Run tests on PR
        └── release.yml                 # Publish to PyPI
```

---

## 7. Data Flow

### 7.1 Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: INPUT INGESTION                                                     │
│  ─────────────────────                                                       │
│  • Read file(s) from path, stream, or API                                    │
│  • Detect encoding (UTF-8, UTF-16, etc.)                                     │
│  • Determine format: JSON vs SQL vs mixed                                  │
│  • For SQL: split into individual statements (preserve comments!)            │
│  • Store raw content in PipelineState.raw_input                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: FORMAT & DIALECT DETECTION                                          │
│  ──────────────────────────────────                                          │
│  • If JSON: validate structure, detect vendor variant                        │
│  • If SQL: invoke detect_dialect skill                                       │
│    - Analyze keywords, syntax patterns, data types                           │
│    - Return: dialect + version + confidence                                 │
│  • Store in PipelineState.detected_format, PipelineState.detected_dialect    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: SCHEMA EXTRACTION (Skill 1)                                         │
│  ─────────────────────────────────                                           │
│  • If JSON: invoke extract_json_schema                                       │
│    - LLM normalizes varying JSON structures into unified model               │
│    - Maps vendor-specific keys to standard model                             │
│  • If SQL: invoke extract_sql_ddl                                            │
│    - LLM parses DDL statements contextually                                   │
│    - Extracts: tables, columns, types, constraints, indexes, views           │
│    - Preserves SQL comments as descriptions                                   │
│  • Output: intermediate SchemaObject stored in PipelineState                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: SEMANTIC ENRICHMENT (Skill 2) — Parallel where possible           │
│  ────────────────────────────────────────                                    │
│  • invoke infer_descriptions: Add human-readable descriptions                │
│  • invoke classify_business_role: Classify each table's role                 │
│  • invoke identify_key_processes: Map tables to business processes           │
│  • invoke infer_purpose: Generate "why this exists" for each table           │
│  • invoke extract_domain: Classify overall domain                             │
│  • All outputs merged into SchemaObject enrichment fields                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: SCHEMA INTELLIGENCE (Skill 3)                                       │
│  ──────────────────────────────────                                          │
│  • invoke map_relationships: Build complete relationship graph               │
│  • invoke detect_patterns: Identify architectural patterns                   │
│  • invoke infer_constraints: Detect missing but likely constraints           │
│  • Outputs: relationships, patterns, inferred constraints added to model     │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: VALIDATION & QUALITY ASSURANCE (Skill 4)                            │
│  ────────────────────────────────────────────                                │
│  • invoke validate_schema: Check consistency, completeness, correctness        │
│  • invoke confidence_scoring: Score every inferred field                     │
│  • invoke suggest_improvements: Identify gaps and suggest fixes              │
│  • If any critical issue found:                                              │
│    - Option A: Retry failed skill with adjusted prompt                       │
│    - Option B: Flag for human review                                         │
│    - Option C: Degrade gracefully (return what we have with warnings)        │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 7: OUTPUT GENERATION                                                   │
│  ─────────────────────                                                       │
│  • Assemble final JSON from PipelineState.final_output                       │
│  • Include: metadata, tables, views, relationships, patterns, insights         │
│  • Attach: confidence scores, validation report, AI suggestions             │
│  • Serialize to JSON with proper formatting                                  │
│  • Optional: Generate additional formats (YAML, Markdown docs, Mermaid ER)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 State Transitions

```
PipelineState Lifecycle:

[INIT] ──► raw_input populated
  │
  ▼
[DETECTED] ──► detected_format, detected_dialect set
  │
  ▼
[EXTRACTED] ──► intermediate_schema populated (tables, columns, raw constraints)
  │
  ▼
[ENRICHED] ──► descriptions, business roles, purposes, domains added
  │
  ▼
[INTELLIGENCE] ──► relationships, patterns, inferred constraints added
  │
  ▼
[VALIDATED] ──► validation report, confidence scores computed
  │
  ▼
[OUTPUT] ──► final_output JSON ready
  │
  ▼
[COMPLETE] / [FAILED] / [DEGRADED]
```

---

## 8. Output JSON Specification

### 8.1 Final Output Schema

```json
{
  "metadata": {
    "schema_info": {
      "name": "string",
      "catalog": "string",
      "description": "string"
    },
    "database_type": "string",
    "database_version": "string",
    "domain": "string",
    "business_role": "string",
    "generated_at": "ISO 8601 timestamp",
    "source_files": ["string"],
    "parser_type": "ai_agent",
    "extraction_confidence": "float (0-1)",
    "enrichment_confidence": "float (0-1)",
    "overall_confidence": "float (0-1)"
  },

  "tables": [
    {
      "table_name": "string",
      "description": "string",
      "description_confidence": "float (0-1)",
      "purpose": "string",
      "purpose_confidence": "float (0-1)",
      "business_role": "string",
      "business_role_confidence": "float (0-1)",
      "key_processes": [
        {
          "process": "string",
          "confidence": "float (0-1)"
        }
      ],
      "table_type": "base_table | view | materialized_view | temp_table | external",
      "detected_patterns": ["string"],

      "columns": [
        {
          "column_name": "string",
          "ordinal_position": "integer",
          "description": "string",
          "description_confidence": "float (0-1)",
          "purpose": "string",
          "business_role": "string",
          "data_type": {
            "native": "string (DB-specific)",
            "standardized": "string (unified type)",
            "precision": "integer | null",
            "scale": "integer | null",
            "nullable": "boolean",
            "inferred_from": "string"
          },
          "default_value": "string | null",
          "constraints": ["string"],
          "properties": {
            "is_identity": "boolean",
            "is_generated": "boolean",
            "is_hidden": "boolean",
            "is_computed": "boolean"
          },
          "statistics": {
            "approx_distinct_values": "integer | null",
            "null_fraction": "float | null"
          }
        }
      ],

      "table_constraints": [
        {
          "constraint_name": "string",
          "constraint_type": "PRIMARY_KEY | FOREIGN_KEY | UNIQUE | CHECK | NOT_NULL | DEFAULT",
          "columns": ["string"],
          "definition": "string (raw SQL)",
          "references": {
            "table": "string",
            "columns": ["string"],
            "on_delete": "CASCADE | SET_NULL | RESTRICT | NO_ACTION",
            "on_update": "CASCADE | SET_NULL | RESTRICT | NO_ACTION"
          },
          "deferrable": "boolean",
          "inferred": "boolean",
          "inferred_confidence": "float (0-1)"
        }
      ],

      "indexes": [
        {
          "index_name": "string",
          "index_type": "btree | hash | gin | gist | fulltext | spatial | other",
          "columns": ["string"],
          "is_unique": "boolean",
          "is_primary": "boolean",
          "is_partial": "boolean",
          "definition": "string (raw SQL)"
        }
      ],

      "relationships": {
        "incoming": [
          {
            "from_table": "string",
            "relationship": "one-to-one | one-to-many | many-to-many",
            "via_columns": ["string"],
            "business_meaning": "string"
          }
        ],
        "outgoing": [
          {
            "to_table": "string",
            "relationship": "many-to-one | one-to-one",
            "via_columns": ["string"],
            "business_meaning": "string"
          }
        ]
      },

      "estimated_row_count": "integer | null",
      "tablespace": "string | null",

      "ai_insights": {
        "likely_missing_index": "string | null",
        "suggested_description_improvement": "string | null",
        "pattern_notes": "string | null",
        "anomalies": ["string"]
      }
    }
  ],

  "views": [
    {
      "view_name": "string",
      "description": "string",
      "purpose": "string",
      "is_materialized": "boolean",
      "definition": "string (raw SQL)",
      "dependencies": ["string"],
      "columns": [
        {
          "column_name": "string",
          "source_column": "string",
          "data_type": {
            "native": "string",
            "standardized": "string"
          }
        }
      ]
    }
  ],

  "schema_intelligence": {
    "detected_patterns": [
      {
        "pattern": "string",
        "affected_tables": ["string"],
        "columns_involved": ["string"],
        "confidence": "float (0-1)"
      }
    ],
    "domain_classification": {
      "primary_domain": "string",
      "confidence": "float (0-1)",
      "secondary_domains": ["string"]
    },
    "suggested_tags": ["string"],
    "relationship_graph": {
      "nodes": "integer",
      "edges": "integer",
      "cycles_detected": "boolean",
      "isolated_tables": ["string"]
    }
  },

  "validation_report": {
    "overall_status": "pass | warn | fail",
    "issues": [
      {
        "severity": "critical | warning | info",
        "category": "consistency | completeness | correctness",
        "message": "string",
        "affected_object": "string",
        "suggestion": "string"
      }
    ],
    "statistics": {
      "tables_processed": "integer",
      "columns_processed": "integer",
      "constraints_extracted": "integer",
      "descriptions_inferred": "integer",
      "average_confidence": "float"
    }
  },

  "ai_suggestions": [
    {
      "category": "description | constraint | index | pattern | documentation",
      "priority": "high | medium | low",
      "message": "string",
      "affected_table": "string | null",
      "affected_column": "string | null"
    }
  ]
}
```

### 8.2 Key Improvements Over Original Spec

| Improvement | Rationale |
|-------------|-----------|
| **Confidence scores on every field** | Transparency — user knows which metadata to trust |
| **Metadata block** | Provenance, traceability, reproducibility |
| **Table-level constraints separate from column constraints** | Some constraints (composite PK, multi-column CHECK) span columns |
| **Indexes section** | Critical for ETL performance understanding |
| **Relationship graph** | Enables downstream schema analysis, migration planning |
| **Views with dependencies** | Views are first-class schema objects |
| **Schema intelligence section** | Patterns, domain, tags — adds value beyond raw extraction |
| **Validation report** | Self-checking quality assurance |
| **AI suggestions** | Proactive guidance for schema improvement |
| **Table type enum** | Distinguishes base tables, views, temp tables, external tables |
| **Properties object** | Structured vs flat boolean flags (extensible) |
| **Inferred flag on constraints** | Distinguishes declared vs AI-inferred metadata |

---

## 9. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
**Goal:** Core framework, models, and basic extraction

| Task | Deliverable |
|------|-------------|
| Set up project structure | `pyproject.toml`, `src/etl_schema_agent/` skeleton |
| Define Pydantic models | `models/schema.py`, `models/output.py` |
| Build orchestrator shell | `core/orchestrator.py` with state management |
| Implement `extract_json_schema` | Handle 3-4 common JSON variants |
| Implement `extract_sql_ddl` (basic) | Parse CREATE TABLE for PostgreSQL + MySQL |
| Build CLI | `typer` app with `process` command |
| Unit tests | Test models, basic extraction |

**Milestone:** Can process simple JSON and SQL files to intermediate model

---

### Phase 2: AI Enrichment (Weeks 3-4)
**Goal:** Semantic layer — descriptions, roles, domain

| Task | Deliverable |
|------|-------------|
| Design LLM prompts | All skill prompts with few-shot examples |
| Implement `infer_descriptions` | Column + table descriptions |
| Implement `classify_business_role` | Table role classification |
| Implement `identify_key_processes` | Business process mapping |
| Implement `infer_purpose` | Table purpose statements |
| Implement `extract_domain` | Domain classification |
| Confidence scoring | Per-field confidence calculation |
| Integration tests | Full pipeline with sample schemas |

**Milestone:** Can enrich a schema with business meaning and confidence scores

---

### Phase 3: Intelligence Layer (Weeks 5-6)
**Goal:** Pattern detection, relationships, inferred constraints

| Task | Deliverable |
|------|-------------|
| Implement `map_relationships` | Complete relationship graph |
| Implement `detect_patterns` | Audit trail, soft delete, multi-tenancy, etc. |
| Implement `infer_constraints` | Missing constraint detection |
| Schema intelligence section | Patterns, domain, tags in output |
| Validation skill | `validate_schema`, `confidence_scoring`, `suggest_improvements` |
| Golden dataset | 5-10 schemas with expected outputs |
| Regression testing | Compare outputs against golden dataset |

**Milestone:** Can detect patterns and suggest improvements

---

### Phase 4: Polish & Scale (Weeks 7-8)
**Goal:** Production readiness, additional dialects, API

| Task | Deliverable |
|------|-------------|
| Add Oracle dialect support | SQL extraction for Oracle |
| Add SQL Server dialect support | SQL extraction for SQL Server |
| Add SQLite dialect support | SQL extraction for SQLite |
| Plugin architecture | `plugins/` with base class + examples |
| FastAPI layer | REST API for agent as a service |
| Docker containerization | `Dockerfile`, `docker-compose.yml` |
| Performance optimization | Caching, batching, async processing |
| Documentation | `docs/`, README, examples |
| CI/CD | GitHub Actions for test + release |

**Milestone:** Production-ready, deployable agent with 5+ dialects

---

### Phase 5: Advanced Features (Post-MVP)
**Goal:** Enterprise features, advanced AI capabilities

| Feature | Description |
|---------|-------------|
| Multi-schema comparison | Diff two schemas semantically |
| Migration planning | Suggest migration path between DB platforms |
| Natural language queries | "Which tables handle payment processing?" |
| Auto-documentation | Generate Markdown/Mermaid docs from output |
| Data quality rules | Infer expected data patterns from schema |
| Schema evolution tracking | Version schemas over time |
| Human-in-the-loop | Interactive refinement when confidence is low |
| Custom skill marketplace | Community-contributed skills |

---

## 10. Risk & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **LLM hallucinates schema elements** | High | Medium | Validation layer + confidence scoring + human review for low confidence |
| **SQL parsing fails on complex/vendor-specific DDL** | High | Medium | Fallback to partial extraction + flag for review; traditional parser as backup |
| **High LLM API costs** | Medium | High | Caching, batching, local LLM option (Ollama), token optimization |
| **Latency for large schemas** | Medium | High | Streaming, parallel skill execution, async processing |
| **Inconsistent output across runs** | Medium | Medium | Temperature=0, deterministic prompts, golden dataset regression tests |
| **Sensitive schema data exposure** | High | Low | Local LLM option, data anonymization pre-processing, audit logging |
| **Skill prompt drift** | Medium | Medium | Versioned prompts, A/B testing, evaluation framework |
| **Dependency on single LLM provider** | Medium | Medium | LiteLLM abstraction, multi-provider support |

---

## 11. Appendix

### A. Type Standardization Registry

| Native Type Family | Standardized Type | Examples |
|-------------------|-------------------|----------|
| Integer variants | `INTEGER` | `INT`, `INTEGER`, `BIGINT`, `SMALLINT`, `TINYINT`, `SERIAL`, `BIGSERIAL` |
| Decimal variants | `DECIMAL` | `DECIMAL`, `NUMERIC`, `NUMBER`, `MONEY`, `DEC` |
| Float variants | `FLOAT` | `FLOAT`, `REAL`, `DOUBLE PRECISION`, `DOUBLE` |
| String variants | `STRING` | `VARCHAR`, `CHAR`, `TEXT`, `NVARCHAR`, `VARCHAR2`, `STRING` |
| Binary variants | `BINARY` | `BLOB`, `BYTEA`, `BINARY`, `VARBINARY` |
| Boolean | `BOOLEAN` | `BOOLEAN`, `BOOL`, `BIT(1)` |
| Date | `DATE` | `DATE` |
| Timestamp | `TIMESTAMP` | `TIMESTAMP`, `DATETIME`, `DATETIME2`, `TIMESTAMPTZ` |
| Time | `TIME` | `TIME`, `TIMETZ` |
| Interval | `INTERVAL` | `INTERVAL` |
| JSON | `JSON` | `JSON`, `JSONB` |
| UUID | `UUID` | `UUID`, `UNIQUEIDENTIFIER` |
| Array | `ARRAY` | `TEXT[]`, `INT[]`, `ARRAY` |
| Enum | `ENUM` | `ENUM`, custom enums |
| Spatial | `SPATIAL` | `GEOMETRY`, `GEOGRAPHY`, `POINT` |
| XML | `XML` | `XML` |

### B. Prompt Design Principles

1. **Few-shot examples:** Include 2-3 examples of input → expected output per skill
2. **Structured output:** Use JSON mode / function calling for parseable results
3. **Chain-of-thought:** Ask LLM to reason before answering (improves accuracy)
4. **Context window:** Include relevant schema context (related tables, constraints)
5. **Self-correction:** Include validation step in prompt ("check your work")
6. **Delineation:** Clear separation between system prompt, context, and task

### C. Example Skill Prompt Template

```
SYSTEM:
You are a database schema extraction expert. Your task is to parse SQL DDL 
statements and extract structured schema information.

CONTEXT:
Database dialect detected: {dialect}
Number of statements: {count}

TASK:
Parse the following SQL DDL statements and extract all schema objects:
- Tables with columns, data types, defaults, constraints
- Indexes
- Views
- Comments (as descriptions)

For each column, identify:
- Native data type (as declared)
- Whether it's nullable
- Default value
- Constraints (PK, FK, Unique, Check, Not Null)

OUTPUT FORMAT:
Return valid JSON matching this schema:
{output_schema}

EXAMPLES:
{few_shot_examples}

SQL TO PARSE:
{sql_content}

REASONING:
First, analyze the SQL structure. Then extract each object systematically. 
Finally, validate completeness against the input.
```

### D. Glossary

| Term | Definition |
|------|------------|
| **DDL** | Data Definition Language — SQL commands that define schema (CREATE, ALTER, DROP) |
| **Dialect** | Database-specific variant of SQL syntax |
| **Enrichment** | Adding semantic meaning (descriptions, roles) beyond raw extraction |
| **Intermediate Representation** | Unified model that all inputs normalize to |
| **Skill** | Self-contained AI module with a specific responsibility |
| **Schema Object** | Any database object: table, view, index, constraint, etc. |
| **Standardized Type** | Database-agnostic type classification |

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-06-22 | AI Assistant | Initial plan — AI-native skills-based architecture |

---

*End of Document*
