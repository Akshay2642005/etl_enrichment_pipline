#!/usr/bin/env python3
"""Entry point — run the API server or execute the enrichment pipeline directly.

Usage:
    uv run main.py                   # start the API server (default)
    uv run main.py api               # same as above
    uv run main.py pipeline <file>   # run the pipeline on a metadata JSON file

For uvicorn directly:
    uv run uvicorn main:app
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from etl_enrichment_pipeline.api.main import app as _app
from etl_enrichment_pipeline.core.pipeline import run_pipeline as _run_pipeline


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger so pipeline node logs appear on stderr.

    Reads ``GLOBAL_PIPELINE["log_level"]`` from config if available, otherwise
    falls back to *level*.
    """
    try:
        from etl_enrichment_pipeline.config.config_global import GLOBAL_PIPELINE

        level = GLOBAL_PIPELINE.get("log_level", level).upper()
    except Exception:
        pass

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

# ---------------------------------------------------------------
# Exposed for:  uv run uvicorn main:app
# ---------------------------------------------------------------
app = _app


def run_api() -> None:
    setup_logging()
    import uvicorn

    uvicorn.run(
        "src.etl_enrichment_pipeline.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


def run_pipeline(file_path: str = "sqlj_son/raw_metadata.json") -> None:
    setup_logging()
    result = _run_pipeline(file_path)

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    out_path = out_dir / "enriched_metadata.json"
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"Written to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ETL Schema Intelligence — API server or CLI pipeline runner",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="api",
        choices=("api", "pipeline"),
        help="Subcommand (default: api)",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="sqlj_son/raw_metadata.json",
        help="Path to raw metadata JSON (pipeline command only)",
    )

    args = parser.parse_args()

    if args.command == "pipeline":
        run_pipeline(args.file)
    else:
        run_api()


if __name__ == "__main__":
    main()
