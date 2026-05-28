from typing import Any, Literal, TypedDict


class PipelineState(TypedDict, total=False):
    source_code: str
    schema_context: str | None
    parse_result: dict[str, Any]
    analysis_result: dict[str, Any]
    generated_code: str
    validation_result: dict[str, Any]
    report: dict[str, Any]
    status: Literal["success", "failure", "partial"]
    error: str | None
    history_id: int | None
