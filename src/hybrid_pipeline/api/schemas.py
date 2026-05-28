from typing import Any, Literal

from pydantic import BaseModel, Field


class ModernizeRequest(BaseModel):
    source_code: str = Field(..., min_length=1)
    schema_context: str | None = None


class ModernizeResponse(BaseModel):
    generated_code: str | None
    report: dict[str, Any]
    status: Literal["success", "failure", "partial"]
    history_id: int | None = None


class HealthResponse(BaseModel):
    status: str
    pipeline: str = "modernization"
    database: str = "unknown"


class MetricsResponse(BaseModel):
    summary: dict[str, Any]
