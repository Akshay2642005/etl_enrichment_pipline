> [!CAUTION]
> **This repository is no longer actively maintained.**
>
> Development has been moved to a new repository under the company's GitHub organization. This repository is retained for historical reference and archival purposes only.
>
> No new features, bug fixes, or security updates will be applied here. Please use the new organization-hosted repository for all future development and contributions.
>
> If you require access to the active repository, contact the project maintainers or your organization administrator.

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
# From a raw metadata JSON file:
uv run main.py pipeline sqlj_son/raw_metadata.json

# From a SQL DDL file:
uv run main.py --sql-file sqlj_son/sample_schema.sql

# From a live database (system_name from config):
uv run main.py --db-connect "Crew Management System"

# Start API server:
uv run main.py
# or
uv run main.py api
```

Output is written to `output/enriched_metadata.json`.

Full help:

```
usage: main.py [-h] [--sql-file PATH | --db-connect NAME]
               [{api,pipeline}] [file]

ETL Schema Intelligence — API server or CLI pipeline runner

positional arguments:
  {api,pipeline}     Subcommand (default: api)
  file               Path to raw metadata JSON (pipeline command only)

options:
  -h, --help         show this help message and exit
  --sql-file PATH    Path to a SQL DDL file to parse and enrich
  --db-connect NAME  Database system name (from config) to extract and enrich
```

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

## LangSmith Tracing (Optional)

[LangSmith](https://smith.langchain.com) provides observability for LangGraph runs —
node latencies, LLM call traces, error tracking, and state diffs.

### Setup

```bash
uv add langsmith
```

Then uncomment these lines in `.env` with your LangSmith API key:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=etl-enrichment-pipeline
```

Run the pipeline once and traces will appear at
[https://smith.langchain.com](https://smith.langchain.com).

### Visualising the Graph Structure

The compiled `StateGraph` has built-in drawing methods:

```python
from etl_enrichment_pipeline.core.pipeline import build_pipeline

graph = build_pipeline()

# ASCII art (no deps)
graph.get_graph().print_ascii()

# Mermaid syntax (renders in GitHub/GitLab Markdown)
print(graph.get_graph().draw_mermaid())

# PNG image (requires: uv add playwright && uv run playwright install chromium)
png = graph.get_graph().draw_mermaid_png()
Path("output/graph.png").write_bytes(png)
```
