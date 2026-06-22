"""Shared fixtures for ETL Schema Intelligence tests."""
import pytest

from etl_enrichment_pipeline.models.canonical import (
    CanonicalSchema,
    ColumnSchema,
    TableSchema,
)


@pytest.fixture
def minimal_canonical_schema():
    return CanonicalSchema(
        tables=[
            TableSchema(
                table_name="patients",
                columns=[
                    ColumnSchema(
                        table_name="patients",
                        column_name="patient_id",
                        data_type="INTEGER",
                        is_primary_key=True,
                    ),
                    ColumnSchema(
                        table_name="patients",
                        column_name="name",
                        data_type="VARCHAR",
                    ),
                    ColumnSchema(
                        table_name="patients",
                        column_name="email",
                        data_type="VARCHAR",
                    ),
                ]
            )
        ]
    )


@pytest.fixture
def empty_pipeline_state():
    from etl_enrichment_pipeline.models.pipeline_state import PipelineState
    return PipelineState()
