"""Etapa 1 — Parsing SQL/PLpgSQL com sqlglot + sqlparse."""

from __future__ import annotations

import re
from typing import Any

import sqlglot
import sqlparse
from sqlglot import exp

_PARAM_RE = re.compile(
    r"\b(IN|OUT|INOUT)\s+(\w+)\s+([\w\[\]()]+)",
    re.IGNORECASE,
)
_ROUTINE_RE = re.compile(
    r"CREATE\s+OR\s+REPLACE\s+(FUNCTION|PROCEDURE)\s+(\w+)\s*\(",
    re.IGNORECASE,
)
_DECLARE_RE = re.compile(r"DECLARE\s+(.*?)\s+BEGIN", re.IGNORECASE | re.DOTALL)
_VAR_LINE_RE = re.compile(r"(\w+)\s+([\w\[\]()]+)\s*(:=.*?)?;", re.IGNORECASE)


def parse_procedure(source_code: str) -> dict[str, Any]:
    """Produz IR estruturada: metadados PL/pgSQL + AST sqlglot por statement."""
    normalized = source_code.strip()
    routine_match = _ROUTINE_RE.search(normalized)
    routine_kind = routine_match.group(1).upper() if routine_match else "UNKNOWN"
    routine_name = routine_match.group(2) if routine_match else "unknown"

    params_block = _extract_params_block(normalized)
    parameters = _PARAM_RE.findall(params_block) if params_block else []
    params = [{"direction": d.upper(), "name": n, "type": t} for d, n, t in parameters]
    if not params and params_block:
        for name, ptype in re.findall(r"(\w+)\s+([\w\[\]()]+)", params_block):
            if name.upper() not in ("IN", "OUT", "INOUT"):
                params.append({"direction": "IN", "name": name, "type": ptype})

    declare_vars: list[dict[str, str]] = []
    declare_match = _DECLARE_RE.search(normalized)
    if declare_match:
        for line in declare_match.group(1).split(";"):
            line = line.strip()
            if not line:
                continue
            vm = _VAR_LINE_RE.match(line)
            if vm:
                declare_vars.append({"name": vm.group(1), "type": vm.group(2)})

    body = _extract_body(normalized)
    statements = _split_plpgsql_statements(body)
    parsed_statements: list[dict[str, Any]] = []

    for idx, stmt in enumerate(statements):
        entry: dict[str, Any] = {
            "index": idx,
            "raw": stmt.strip(),
            "kind": _classify_statement(stmt),
        }
        if entry["kind"] in ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH"):
            try:
                ast = sqlglot.parse_one(stmt, dialect="postgres")
                entry["sqlglot_ast"] = ast.sql(dialect="postgres")
                entry["sqlglot_type"] = type(ast).__name__
            except Exception as exc:  # noqa: BLE001
                entry["parse_error"] = str(exc)
        parsed_statements.append(entry)

    tokens = [
        {"type": t.ttype.__class__.__name__ if t.ttype else "Text", "value": t.value}
        for t in sqlparse.parse(normalized)[0].flatten()
        if t.value.strip()
    ][:200]

    return {
        "routine_kind": routine_kind,
        "routine_name": routine_name,
        "parameters": params,
        "declare_variables": declare_vars,
        "statements": parsed_statements,
        "token_sample": tokens,
        "dialect": "postgres",
        "parser_libraries": ["sqlglot", "sqlparse"],
    }


def _extract_params_block(sql: str) -> str:
    start = sql.find("(")
    if start < 0:
        return ""
    depth = 0
    for i, ch in enumerate(sql[start:], start):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return sql[start + 1 : i]
    return ""


def _extract_body(sql: str) -> str:
    m = re.search(r"\$\$\s*(.*)\s*\$\$", sql, re.IGNORECASE | re.DOTALL)
    if m:
        inner = m.group(1)
        inner = re.sub(r"^DECLARE.*?BEGIN", "", inner, count=1, flags=re.IGNORECASE | re.DOTALL)
        inner = re.sub(r"\bEND\s*;\s*$", "", inner.strip(), flags=re.IGNORECASE)
        return inner
    return sql


def _split_plpgsql_statements(body: str) -> list[str]:
    """Separa statements de alto nível respeitando blocos BEGIN/EXCEPTION."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for line in body.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if re.match(r"BEGIN\b", upper):
            depth += 1
        if depth > 0 or not stripped.startswith(("IF ", "FOR ", "LOOP", "OPEN ", "CLOSE ")):
            current.append(line)
        if re.match(r"END\s*;", upper) or re.match(r"END\s+LOOP\s*;", upper):
            depth = max(0, depth - 1)
            if depth == 0 and current:
                parts.append("\n".join(current))
                current = []
        elif stripped.endswith(";") and depth <= 1 and "LOOP" not in upper:
            current.append(line)
            parts.append("\n".join(current))
            current = []
    if current:
        parts.append("\n".join(current))
    return [p for p in parts if p.strip()]


def _classify_statement(stmt: str) -> str:
    s = stmt.strip().upper()
    for kw in (
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "WITH",
        "OPEN",
        "FETCH",
        "CLOSE",
        "RAISE",
        "RETURN",
        "GET DIAGNOSTICS",
        "EXCEPTION",
        "IF",
        "LOOP",
        "CASE",
    ):
        if s.startswith(kw) or f" {kw} " in f" {s} ":
            return kw.split()[0] if kw != "GET DIAGNOSTICS" else "GET_DIAGNOSTICS"
    if "CURSOR" in s:
        return "CURSOR"
    return "OTHER"


def extract_tables_from_ast(stmt: str) -> set[str]:
    try:
        tree = sqlglot.parse_one(stmt, dialect="postgres")
        return {t.name for t in tree.find_all(exp.Table) if t.name}
    except Exception:  # noqa: BLE001
        return set()
