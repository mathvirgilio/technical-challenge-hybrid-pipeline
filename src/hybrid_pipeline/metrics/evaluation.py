"""Métrica de evaluation: taxa de ast.parse no código gerado."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hybrid_pipeline.graph.build import graph
from hybrid_pipeline.persistence.repository import ModernizationRepository


async def evaluate_fixtures(
    fixtures_dir: Path,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    schema = (
        schema_path.read_text(encoding="utf-8") if schema_path and schema_path.exists() else None
    )
    repo = ModernizationRepository()
    results: list[dict[str, Any]] = []

    for sql_file in sorted(fixtures_dir.glob("annex_*.sql")):
        if sql_file.name == "annex_a_schema.sql":
            continue
        source = sql_file.read_text(encoding="utf-8")
        final = await graph.ainvoke(
            {"source_code": source, "schema_context": schema},
        )
        validation = final.get("validation_result") or {}
        rate = validation.get("metrics", {}).get("ast_parse_rate", 0.0)
        status = final.get("status", "failure")
        routine = (final.get("parse_result") or {}).get("routine_name", sql_file.stem)
        repo.save_metric(routine, rate, status)
        results.append(
            {
                "fixture": sql_file.name,
                "routine_name": routine,
                "status": status,
                "ast_parse_rate": rate,
                "valid": validation.get("valid", False),
            }
        )

    rates = [r["ast_parse_rate"] for r in results]
    summary = {
        "procedures_evaluated": len(results),
        "mean_ast_parse_rate": sum(rates) / len(rates) if rates else 0.0,
        "success_count": sum(1 for r in results if r["status"] == "success"),
        "details": results,
    }
    return summary
