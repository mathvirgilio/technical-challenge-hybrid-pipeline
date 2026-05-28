"""Nós LangGraph da pipeline."""

from __future__ import annotations

from typing import Any

from hybrid_pipeline.graph.state import PipelineState
from hybrid_pipeline.persistence.repository import ModernizationRepository
from hybrid_pipeline.pipeline.analysis import analyze_semantics
from hybrid_pipeline.pipeline.generation import fix_function_name, generate_python
from hybrid_pipeline.pipeline.parsing import parse_procedure
from hybrid_pipeline.pipeline.validation import validate_python


def parsing_node(state: PipelineState) -> dict[str, Any]:
    source = state["source_code"]
    try:
        result = parse_procedure(source)
        return {"parse_result": result, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {
            "parse_result": {"error": str(exc)},
            "error": str(exc),
            "status": "failure",
        }


def analysis_node(state: PipelineState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    parse_result = state.get("parse_result", {})
    analysis = analyze_semantics(state["source_code"], parse_result)
    return {"analysis_result": analysis}


def generation_node(state: PipelineState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    gen = generate_python(
        state["source_code"],
        state.get("parse_result", {}),
        state.get("analysis_result", {}),
        state.get("schema_context"),
    )
    code = fix_function_name(gen["generated_code"], state.get("parse_result", {}))
    return {
        "generated_code": code,
        "generation_meta": {k: v for k, v in gen.items() if k != "generated_code"},
    }


def validation_node(state: PipelineState) -> dict[str, Any]:
    if state.get("error"):
        report = _build_report(state)
        history_id = _persist({**state, "report": report, "status": "failure"}, report)
        return {
            "validation_result": {},
            "report": report,
            "status": "failure",
            "history_id": history_id,
        }

    code = state.get("generated_code", "")
    validation = validate_python(code)
    status: str = "success"
    if not validation["valid"]:
        status = "partial" if validation.get("ast_parse_ok") else "failure"
    if state.get("error"):
        status = "failure"

    report = _build_report({**state, "validation_result": validation})
    merged = {**state, "validation_result": validation, "report": report, "status": status}
    history_id = _persist(merged, report)

    return {
        "validation_result": validation,
        "report": report,
        "status": status,
        "history_id": history_id,
    }


def _build_report(state: PipelineState) -> dict[str, Any]:
    return {
        "parsing": state.get("parse_result"),
        "analysis": state.get("analysis_result"),
        "generation": state.get("generation_meta") or {},
        "validation": state.get("validation_result"),
        "status": state.get("status"),
        "error": state.get("error"),
    }


def _persist(state: PipelineState, report: dict[str, Any]) -> int | None:
    try:
        repo = ModernizationRepository()
        return repo.save(
            source_code=state.get("source_code", ""),
            generated_code=state.get("generated_code"),
            report=report,
            status=state.get("status", "failure"),
        )
    except Exception:  # noqa: BLE001
        return None
