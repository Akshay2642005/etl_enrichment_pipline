"""ETL Schema Intelligence API — FastAPI application."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from datetime import datetime
import tempfile
from typing import Any
from etl_enrichment_pipeline.core.pipeline import run_pipeline
from etl_enrichment_pipeline.agents.extraction_agent import extract_schema_generic
from etl_enrichment_pipeline.agents.ddl_parser import ddl_to_json

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


@app.post("/extract")
async def extract_metadata(request: Request) -> JSONResponse:
    """Extract metadata from a database and save it to sql_json."""
    try:
        body = await request.json()
        db_type = body.get("database_type")
        creds = body.get("credentials", {})
        
        if not db_type:
            return JSONResponse(content={"error": "database_type is required"}, status_code=400)
            
        # Run extraction
        schema_dict = extract_schema_generic(db_type, creds)
        
        # Save to sql_json folder
        out_dir = Path("sql_json")
        out_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = out_dir / f"{db_type}_schema_{timestamp}.json"
        
        out_file.write_text(json.dumps(schema_dict, indent=2, default=str), encoding="utf-8")
        
        return JSONResponse(
            content={
                "message": f"Successfully extracted and saved to {out_file.name}",
                "file_path": str(out_file),
                "data": schema_dict
            },
            status_code=200
        )
    except Exception as exc:
        return JSONResponse(
            content={"error": "Extraction failed", "detail": str(exc)},
            status_code=500
        )


@app.post("/parse-sql")
async def parse_sql(request: Request) -> JSONResponse:
    """Parse raw SQL DDL text and save to sql_json."""
    try:
        body = await request.json()
        sql_text = body.get("sql_text")
        db_type = body.get("database_type", "postgresql")
        schema_name = body.get("schema", "public")
        
        if not sql_text:
            return JSONResponse(content={"error": "sql_text is required"}, status_code=400)
            
        # Write sql_text to a temporary file so ddl_to_json can read it
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False, encoding="utf-8") as tmp:
            tmp.write(sql_text)
            tmp_path = tmp.name
            
        try:
            # Parse the SQL
            schema_dict = ddl_to_json(tmp_path, database_type=db_type, schema=schema_name)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
            
        # Save to sql_json folder
        out_dir = Path("sql_json")
        out_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = out_dir / f"{db_type}_ddl_{timestamp}.json"
        
        out_file.write_text(json.dumps(schema_dict, indent=2, default=str), encoding="utf-8")
        
        return JSONResponse(
            content={
                "message": f"Successfully parsed SQL and saved to {out_file.name}",
                "file_path": str(out_file),
                "data": schema_dict
            },
            status_code=200
        )
    except Exception as exc:
        return JSONResponse(
            content={"error": "SQL Parsing failed", "detail": str(exc)},
            status_code=500
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
