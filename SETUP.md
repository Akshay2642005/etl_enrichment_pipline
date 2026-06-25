# NL-to-SQL Service — Setup Guide

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager)
- PostgreSQL 15+ with pgvector extension
- Neo4j 5+ (local Docker or Neo4j Aura cloud)
- An LLM API key (OpenRouter, OpenAI, or Ollama local)

---

## 1. Install Dependencies

```bash
cd etl_enrichment_pipline
uv sync
```

---

## 2. Environment Variables

Create `.env` in the project root (`etl_enrichment_pipline/.env`):

```env
# --- LLM Configuration ---
# Choose ONE provider:

# Option A: OpenRouter (free tier available)
LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
OPENAI_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://openrouter.ai/api/v1

# Option B: OpenAI
# LLM_MODEL=gpt-4o
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx

# Option C: Ollama (local)
# LLM_MODEL=llama3
# OPENAI_BASE_URL=http://localhost:11434/v1
# OPENAI_API_KEY=ollama

LLM_TIMEOUT=300

# --- PostgreSQL / pgvector ---
PGVECTOR_DSN=postgresql://postgres:postgres@localhost:5432/schema_embeddings

# --- Neo4j ---
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# --- Embedding Model ---
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# --- Metadata ---
METADATA_PATH=etl_enrichment_pipline/output/enriched_metadata.json
```

---

## 3. Database Setup

### 3a. PostgreSQL + pgvector

**Option A — Local install:**
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib
sudo -u postgres psql -c "CREATE DATABASE schema_embeddings;"
sudo -u postgres psql -d schema_embeddings -c "CREATE EXTENSION vector;"

# macOS (Homebrew)
brew install postgresql@15
createdb schema_embeddings
psql -d schema_embeddings -c "CREATE EXTENSION vector;"
```

**Option B — Docker:**
```bash
docker run -d \
  --name pgvector \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=schema_embeddings \
  -p 5432:5432 \
  pgvector/pgvector:0.8.0-pg17
```

The service auto-creates the `schema_embeddings` table and HNSW index.

### 3b. Neo4j

**Option A — Docker:**
```bash
docker run -d \
  --name neo4j \
  -e NEO4J_AUTH=neo4j/password \
  -p 7687:7687 \
  -p 7474:7474 \
  neo4j:5-community
```

**Option B — Neo4j Aura (cloud):**
1. Create a free AuraDB instance at https://console.neo4j.io
2. Get the connection URI (e.g. `neo4j+s://xxxxxxxx.databases.neo4j.io`)
3. Update `.env`:
   ```env
   NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your-aura-password
   ```

---

## 4. Load Embeddings

```bash
cd etl_enrichment_pipline
python -m scripts.generate_embeddings
```

Expected output:
```
Loading metadata from etl_enrichment_pipline/output/enriched_metadata.json...
  Loaded 30 tables, 121 columns, 31 FK relationships, 4 entity relationships
Initializing EmbeddingService...
Generating embeddings for schema objects...
  Generated 30 table embeddings
  Generated 121 column embeddings
  Generated 35 relationship embeddings
Initializing VectorStore (pgvector)...
  Schema initialized
  Upserted 186 embeddings to pgvector
  VectorStore connection closed
Initializing GraphStore (Neo4j)...
  Schema constraints created
  Schema loaded into Neo4j
  GraphStore connection closed

Embedded 30 tables, 121 columns, 35 relationships
```

---

## 5. Start the API

```bash
cd etl_enrichment_pipline
uvicorn src.etl_enrichment_pipeline.api.main:app --reload --port 8000
```

---

## 6. Test It

### 6a. Health check
```bash
curl http://localhost:8000/api/v1/nl2sql/health
```

Expected: `{"status": "ok", "service": "nl2sql", "version": "0.1.0"}`

### 6b. Generate SQL
```bash
curl -X POST http://localhost:8000/api/v1/nl2sql \
  -H "Content-Type: application/json" \
  -d '{"question": "Show employees in HR department", "include_explanation": true}'
```

### 6c. Sample questions
```
"List flights with delayed status"
"Count baggage per flight"
"Find equipment needing maintenance in the next 7 days"
"Show turnaround tasks for flight AA123"
```

### 6d. Error cases
```bash
curl -X POST http://localhost:8000/api/v1/nl2sql \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## 7. Run Tests

```bash
cd etl_enrichment_pipline
python -m pytest tests/ -v --tb=short
```

Expected: **113 passed** (76 unit + 10 integration + 27 existing).

---

## 8. Architecture Overview

```
User Question → Embedding Service → Vector Store (pgvector)
                                    → Graph Store (Neo4j)
                                    → Context Builder
                                    → NL-to-SQL Generator (LLM)
                                    → SQL Validator (sqlglot)
                                    → SQL Response
```

---

## 9. File Reference

| Path | Purpose |
|------|---------|
| `core/embedding_service.py` | Embedding generation |
| `core/vector_store.py` | pgvector CRUD |
| `core/graph_store.py` | Neo4j graph operations |
| `core/sql_validator.py` | SQL syntax + metadata validation |
| `core/context_builder.py` | Hybrid vector+graph context assembly |
| `agents/nl2sql_generator.py` | LLM prompt + SQL generation |
| `api/nl2sql_service.py` | FastAPI router |
| `scripts/generate_embeddings.py` | One-time embedding loader |
| `tests/unit/` | 76 unit tests |
| `tests/integration/` | 10 integration tests |
| `output/enriched_metadata.json` | Source schema metadata (30 tables) |

---

## 10. Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|------|
| Connection refused on pgvector | PostgreSQL not running | `docker start pgvector` or check DSN |
| Auth error on Neo4j | Wrong credentials | Check NEO4J_USER/PASSWORD in `.env` |
| LLM returns empty SQL | Missing or invalid API key | Check OPENAI_API_KEY and LLM_MODEL |
| Embeddings not found | Generation not run | Run `python -m scripts.generate_embeddings` |
