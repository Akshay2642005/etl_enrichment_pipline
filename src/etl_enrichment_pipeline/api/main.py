"""ETL Schema Intelligence API — FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

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


__all__ = ["app"]
