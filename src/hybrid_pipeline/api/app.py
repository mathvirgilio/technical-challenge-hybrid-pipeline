"""FastAPI — rotas customizadas para langgraph dev (/health, /modernize, /metrics)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

from hybrid_pipeline.api.schemas import (
    HealthResponse,
    MetricsResponse,
    ModernizeRequest,
    ModernizeResponse,
)
from hybrid_pipeline.graph.build import graph
from hybrid_pipeline.metrics.evaluation import evaluate_fixtures
from hybrid_pipeline.persistence.db import get_connection, init_database


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    try:
        init_database()
    except Exception:  # noqa: BLE001
        pass  # permite subir API antes do Postgres em dev
    yield


app = FastAPI(
    title="Hybrid SQL→Python Pipeline",
    description="Modernização PL/pgSQL → Python 3.14 via LangGraph",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_status = "ok"
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
    except Exception:  # noqa: BLE001
        db_status = "unavailable"
    return HealthResponse(status="ok", database=db_status)


@app.post("/modernize", response_model=ModernizeResponse)
async def modernize(body: ModernizeRequest) -> ModernizeResponse:
    try:
        result = await graph.ainvoke(
            {
                "source_code": body.source_code,
                "schema_context": body.schema_context,
            }
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ModernizeResponse(
        generated_code=result.get("generated_code"),
        report=result.get("report") or {},
        status=result.get("status", "failure"),
        history_id=result.get("history_id"),
    )


@app.get("/metrics/evaluation", response_model=MetricsResponse)
async def metrics_evaluation() -> MetricsResponse:
    root = Path(__file__).resolve().parents[3]
    fixtures = root / "fixtures"
    schema = fixtures / "annex_a_schema.sql"
    if not fixtures.exists():
        raise HTTPException(status_code=404, detail="fixtures/ não encontrado")
    summary = await evaluate_fixtures(fixtures, schema)
    return MetricsResponse(summary=summary)
