# ETL Schema Intelligence

AI-powered pipeline that ingests raw database metadata and enriches it with business context — descriptions, domains, semantic types, business roles, entity relationships, sample queries, and more.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager)
- An LLM provider — the project defaults to **Ollama** (local)

## Setup

```bash
# Clone & enter the project
cd etl_enrichment_pipline

# Install dependencies
uv sync

# Configure your LLM provider
# Edit .env — the default uses Ollama with qwen2.5:3b
OPENAI_API_KEY="ollama"
OPENAI_BASE_URL="http://localhost:11434/v1"
LLM_MODEL="qwen2.5:3b"
LLM_TIMEOUT=120

# If using Ollama, make sure your model is pulled
ollama pull qwen2.5:3b
```

See `.env.template` for alternative providers (OpenAI, Groq, OpenRouter, Azure).

## Usage

### Run the API server

```bash
uv run main.py
# or
uv run main.py api
# or directly with uvicorn
uv run uvicorn main:app
```

The server starts at `http://localhost:8000` with auto-reload.

### Run the pipeline directly (CLI)

```bash
uv run main.py pipeline sqlj_son/raw_metadata.json
```

Output is written to `output/enriched_metadata.json`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/enrich` | Accept raw metadata JSON, run the pipeline, return enriched output |

### POST /enrich

```bash
curl -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d @sqlj_son/raw_metadata.json
```

## Project Structure

```
src/
  etl_enrichment_pipeline/
    api/
      main.py            # FastAPI app
    agents/              # Pipeline agent nodes
    core/
      pipeline.py        # LangGraph pipeline runner
      llm.py             # LLM client
    models/              # Pydantic schemas
    config/              # DB configs
    rules/               # YAML rule files
tests/
main.py                  # CLI entry point (api / pipeline)
```

## Testing

```bash
uv run pytest
```

## Configuration

All config is via environment variables (`.env`):

- `OPENAI_API_KEY` — API key (use `"ollama"` for Ollama)
- `OPENAI_BASE_URL` — API base URL
- `LLM_MODEL` — Model name
- `LLM_TIMEOUT` — Request timeout in seconds
