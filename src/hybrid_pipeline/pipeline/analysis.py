"""Etapa 2 — Análise semântica e pontos de risco."""

from __future__ import annotations

import re
from typing import Any

_RISK_PATTERNS: list[tuple[str, str, str]] = [
    (r"\bCURSOR\b", "cursor", "Cursores podem gerar N+1; preferir bulk/set-based."),
    (r"\bFOR\s+UPDATE\b", "for_update", "Bloqueio de linha — replicar transação no destino."),
    (r"\bRAISE\s+(EXCEPTION|NOTICE|WARNING)\b", "raise", "Mapear para exceções/logging Python."),
    (r"\bJSONB\b|\bjsonb_", "jsonb", "Usar dict/JSON nativo ou psycopg Json."),
    (r"\bWITH\s+RECURSIVE\b", "recursive_cte", "Manter SQL no SGBD ou reescrever iterativamente."),
    (r"\bRETURN\s+QUERY\b", "return_query", "Retorno tabular — usar list[dict] ou pandas."),
    (r"\bEXCEPTION\b", "exception_block", "Traduzir try/except com rollback."),
    (r"\bGET\s+DIAGNOSTICS\b", "row_count", "Usar cursor.rowcount após DML."),
    (r"\b(IN|OUT)\b", "parameters", "Expor IN/OUT como assinatura + retorno estruturado."),
    (r"\bfn_\w+\s*\(", "nested_function", "Inlining ou import do módulo Python equivalente."),
    (r"\bLOOP\b", "loop", "Verificar equivalência semântica em iterações."),
    (
        r"\bTRANSACTION\b|\bCOMMIT\b|\bROLLBACK\b",
        "transaction",
        "Gerenciar via connection.transaction().",
    ),
]


def analyze_semantics(source_code: str, parse_result: dict[str, Any]) -> dict[str, Any]:
    upper = source_code.upper()
    features: dict[str, bool] = {
        "has_cursor": "CURSOR" in upper,
        "has_transaction": "FOR UPDATE" in upper or "BEGIN" in upper,
        "has_exception": "EXCEPTION" in upper,
        "has_cte": "WITH" in upper,
        "has_recursive_cte": "WITH RECURSIVE" in upper,
        "has_jsonb": "JSONB" in upper or "JSONB_" in upper,
        "has_raise": bool(re.search(r"\bRAISE\b", upper)),
        "has_return_query": "RETURN QUERY" in upper,
        "has_out_params": any(
            p.get("direction") == "OUT" for p in parse_result.get("parameters", [])
        ),
        "has_in_params": bool(parse_result.get("parameters")),
        "has_nested_call": bool(re.search(r"\bfn_\w+\s*\(", source_code, re.IGNORECASE)),
        "has_loop": "LOOP" in upper,
        "has_case": "CASE" in upper and "END CASE" in upper,
        "has_bulk_update": "UPDATE" in upper,
        "is_function": parse_result.get("routine_kind") == "FUNCTION",
        "is_procedure": parse_result.get("routine_kind") == "PROCEDURE",
    }

    risks: list[dict[str, str]] = []
    for pattern, tag, message in _RISK_PATTERNS:
        if re.search(pattern, source_code, re.IGNORECASE):
            risks.append({"tag": tag, "severity": _severity(tag), "message": message})

    recommendations: list[str] = []
    if features["has_cursor"]:
        recommendations.append(
            "Preferir carregamento em lote (fetchall) ou query set-based "
            "em vez de FETCH linha a linha."
        )
    if features["has_recursive_cte"] or features["has_return_query"]:
        recommendations.append(
            "Manter CTE/RETURN QUERY como SQL parametrizado via psycopg/SQLAlchemy Core."
        )
    if features["has_transaction"] or features["has_exception"]:
        recommendations.append(
            "Usar context manager de transação (psycopg connection.transaction())."
        )
    if features["has_out_params"]:
        recommendations.append("Retornar OUT parameters como dataclass ou dict nomeado.")

    return {
        "features": features,
        "risks": risks,
        "recommendations": recommendations,
        "complexity_score": _complexity_score(features, len(risks)),
        "sql_delegation_strategy": _delegation_strategy(features),
    }


def _severity(tag: str) -> str:
    high = {"cursor", "recursive_cte", "for_update", "return_query", "exception_block"}
    medium = {"raise", "jsonb", "nested_function", "transaction"}
    if tag in high:
        return "high"
    if tag in medium:
        return "medium"
    return "low"


def _complexity_score(features: dict[str, bool], risk_count: int) -> int:
    score = risk_count
    for key in features:
        if features[key] and key.startswith("has_"):
            score += 1
    return min(score, 20)


def _delegation_strategy(features: dict[str, bool]) -> str:
    if features["has_recursive_cte"] or features["has_return_query"]:
        return "hybrid_sql_in_db"
    if features["has_cursor"] and features["has_loop"]:
        return "hybrid_bulk_python"
    if features["has_bulk_update"] and not features["has_cursor"]:
        return "sqlalchemy_dml_with_python_validation"
    return "python_orchestration_sql_queries"
