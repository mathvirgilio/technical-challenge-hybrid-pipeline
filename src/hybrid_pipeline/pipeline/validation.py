"""Etapa 4 — Validação estática do Python gerado."""

from __future__ import annotations

import ast
import re
from typing import Any


def validate_python(generated_code: str) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    if not generated_code or not generated_code.strip():
        return {
            "valid": False,
            "ast_parse_ok": False,
            "lint_ok": False,
            "issues": ["Código gerado vazio"],
            "warnings": warnings,
            "metrics": {"ast_parse_rate": 0.0},
        }

    ast_ok = False
    try:
        ast.parse(generated_code)
        ast_ok = True
    except SyntaxError as exc:
        issues.append(f"SyntaxError: {exc}")

    lint_ok, lint_issues = _basic_lint(generated_code)
    issues.extend(lint_issues)

    if "NotImplementedError" in generated_code:
        warnings.append("Contém NotImplementedError — migração parcial.")
    if "TODO" in generated_code:
        warnings.append("Contém marcadores TODO.")

    valid = ast_ok and lint_ok and "NotImplementedError" not in generated_code

    return {
        "valid": valid,
        "ast_parse_ok": ast_ok,
        "lint_ok": lint_ok,
        "issues": issues,
        "warnings": warnings,
        "metrics": {
            "ast_parse_rate": 1.0 if ast_ok else 0.0,
            "line_count": len(generated_code.splitlines()),
        },
    }


def _basic_lint(code: str) -> tuple[bool, list[str]]:
    """Lint leve sem depender de subprocess ruff no grafo."""
    issues: list[str] = []
    lines = code.splitlines()
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            issues.append(f"Linha {i} excede 120 caracteres")
        if re.search(r"\bprint\(", line) and "Saldo atual" not in line:
            pass  # permitir RAISE NOTICE → print no relatório
    trailing_imports = sum(1 for line in lines if line.strip().startswith("import "))
    if trailing_imports > 3:
        issues.append("Muitos imports inline — considerar refatoração")
    return len(issues) == 0, issues
