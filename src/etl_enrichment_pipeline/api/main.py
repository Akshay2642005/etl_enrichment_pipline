"""ETL Schema Intelligence API — FastAPI application."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from etl_enrichment_pipeline.core.pipeline import run_pipeline

app = FastAPI(
    title="ETL Schema Intelligence",
    description="AI-powered Schema Intelligence Platform API",
    version="0.1.0",
)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        content={
            "status": "ok",
            "service": "etl-enrichment-pipeline",
            "version": "0.1.0",
        },
        status_code=200,
    )


@app.post("/enrich")
async def enrich(request: Request) -> JSONResponse:
    """Accept a raw metadata JSON body, run the enrichment pipeline, and return
    the enriched output.

    The request body should match the ``raw_metadata.json`` format:

    .. code-block:: json

        {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [ ... ]
        }

    The pipeline is executed synchronously.  If an error occurs during
    processing a 500 response with error details is returned.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception as exc:
        return JSONResponse(
            content={
                "error": "Invalid JSON body",
                "detail": str(exc),
            },
            status_code=400,
        )

    # Write the body to a temporary file so ``run_pipeline`` can read it
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            json.dump(body, tmp)
            tmp_path = tmp.name

        result = run_pipeline(tmp_path)
        return JSONResponse(content=result, status_code=200)

    except Exception as exc:
        return JSONResponse(
            content={
                "error": "Pipeline execution failed",
                "detail": str(exc),
            },
            status_code=500,
        )
    finally:
        # Clean up the temporary file
        if tmp_path is not None:
            tmp_path_obj = Path(tmp_path)
            if tmp_path_obj.exists():
                tmp_path_obj.unlink(missing_ok=True)


__all__ = ["app"]
