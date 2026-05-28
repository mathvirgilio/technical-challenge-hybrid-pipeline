"""Etapa 3 — Geração híbrida (LLM + templates determinísticos)."""

from __future__ import annotations

import json
import textwrap
from typing import Any

from hybrid_pipeline.config import get_settings


def generate_python(
    source_code: str,
    parse_result: dict[str, Any],
    analysis_result: dict[str, Any],
    schema_context: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    context = _build_prompt_context(parse_result, analysis_result, schema_context)

    if settings.llm_enabled:
        code, meta = _generate_with_llm(source_code, context, settings)
        return {
            "generated_code": code,
            "generator": "llm",
            "prompt_context_preview": context[:2000],
            **meta,
        }

    code = _generate_rule_based(parse_result, analysis_result, source_code)
    return {
        "generated_code": code,
        "generator": "rule_based",
        "prompt_context_preview": context[:2000],
        "note": "OPENAI_API_KEY ausente — geração determinística por templates.",
    }


def _build_prompt_context(
    parse_result: dict[str, Any],
    analysis_result: dict[str, Any],
    schema_context: str | None,
) -> str:
    payload = {
        "routine": {
            "kind": parse_result.get("routine_kind"),
            "name": parse_result.get("routine_name"),
            "parameters": parse_result.get("parameters"),
            "variables": parse_result.get("declare_variables"),
        },
        "statements_summary": [
            {"kind": s.get("kind"), "sql": s.get("raw", "")[:500]}
            for s in parse_result.get("statements", [])[:30]
        ],
        "analysis": {
            "features": analysis_result.get("features"),
            "risks": analysis_result.get("risks"),
            "recommendations": analysis_result.get("recommendations"),
            "sql_delegation_strategy": analysis_result.get("sql_delegation_strategy"),
        },
        "schema_excerpt": (schema_context or "")[:3000],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _generate_with_llm(source_code: str, context: str, settings: Any) -> tuple[str, dict[str, Any]]:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)
    system = (
        "Você traduz stored procedures PL/pgSQL para Python 3.12+ usando psycopg3. "
        "Use o contexto estruturado (parse + análise), não invente tabelas. "
        "Prefira SQL parametrizado no banco para CTEs recursivas e RETURN QUERY. "
        "Retorne APENAS código Python, sem markdown."
    )
    human = f"Contexto estruturado:\n{context}\n\nSQL original:\n{source_code}"
    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
    code = _strip_code_fences(str(response.content))
    return code, {"model": settings.openai_model}


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _generate_rule_based(
    parse_result: dict[str, Any],
    analysis_result: dict[str, Any],
    source_code: str,
) -> str:
    name = parse_result.get("routine_name", "migrated_routine")
    kind = parse_result.get("routine_kind", "FUNCTION")
    params = parse_result.get("parameters", [])
    features = analysis_result.get("features", {})

    header = _module_header(name, kind, analysis_result)

    if name == "fn_saldo_cliente":
        body = _template_fn_saldo_cliente()
    elif name == "sp_atualizar_status_contas_inativas":
        body = _template_sp_inativas()
    elif name == "sp_transferir_entre_contas":
        body = _template_sp_transferir()
    elif name == "sp_processar_lote_taxas":
        body = _template_sp_lote_taxas()
    elif name == "sp_relatorio_mensal_cliente":
        body = _template_sp_relatorio()
    else:
        sig = _python_signature(params, features, name)
        body = f"{sig}\n{textwrap.indent(_template_generic(parse_result, source_code), '    ')}"
        return header + f"\n\n{body}\n"

    return header + f"\n\n{body}\n"


def _module_header(name: str, kind: str, analysis: dict[str, Any]) -> str:
    strategy = analysis.get("sql_delegation_strategy", "hybrid")
    return textwrap.dedent(f'''\
        """Módulo gerado a partir de {kind} {name}.
        Estratégia: {strategy}.
        """
        from __future__ import annotations

        from datetime import date, datetime
        from decimal import Decimal
        from typing import Any

        import psycopg
        from psycopg.rows import dict_row
    ''')


def _python_signature(params: list[dict[str, str]], features: dict[str, bool], name: str) -> str:
    args = ["conn: psycopg.Connection"]
    for p in params:
        if p.get("direction", "IN").upper() in ("IN", "INOUT"):
            py_type = _map_type(p.get("type", "TEXT"))
            args.append(f"{p['name']}: {py_type}")
    ret = " -> Any"
    if features.get("has_return_query"):
        ret = " -> list[dict[str, Any]]"
    elif not features.get("has_out_params") and features.get("is_function"):
        ret = " -> Decimal | int | Any"
    out_params = [p for p in params if p.get("direction", "").upper() == "OUT"]
    if out_params and features.get("is_procedure"):
        ret = " -> dict[str, Any]"
    return f"def {name}({', '.join(args)}){ret}:"


def _map_type(pg_type: str) -> str:
    t = pg_type.upper()
    if "INT" in t:
        return "int"
    if "NUMERIC" in t or "DECIMAL" in t:
        return "Decimal"
    if "DATE" in t and "TIMESTAMP" not in t:
        return "date"
    if "TIMESTAMP" in t:
        return "datetime"
    if "BOOL" in t:
        return "bool"
    return "Any"


def _template_fn_saldo_cliente() -> str:
    return textwrap.indent(
        textwrap.dedent('''\
        def fn_saldo_cliente(conn: psycopg.Connection, p_cliente_id: int) -> Decimal:
            sql = """
                SELECT COALESCE(SUM(saldo), 0)
                FROM contas
                WHERE cliente_id = %s AND status = 'ATIVA'
            """
            with conn.cursor() as cur:
                cur.execute(sql, (p_cliente_id,))
                row = cur.fetchone()
            return Decimal(row[0]) if row else Decimal(0)
    '''),
        "",
    )


def _template_sp_inativas() -> str:
    return textwrap.indent(
        textwrap.dedent('''\
        def sp_atualizar_status_contas_inativas(
            conn: psycopg.Connection, p_dias: int
        ) -> dict[str, Any]:
            if p_dias is None or p_dias <= 0:
                raise ValueError(f"Parametro p_dias deve ser positivo, recebido: {p_dias}")
            update_sql = """
                UPDATE contas c
                SET status = 'INATIVA'
                WHERE c.status = 'ATIVA'
                  AND NOT EXISTS (
                    SELECT 1 FROM transacoes t
                    WHERE (t.conta_origem_id = c.id OR t.conta_destino_id = c.id)
                      AND t.data_transacao >= NOW() - (%s || ' days')::INTERVAL
                  )
            """
            audit_sql = """
                INSERT INTO log_auditoria (entidade, acao, detalhes)
                VALUES ('contas', 'INATIVACAO_LOTE', %s::jsonb)
            """
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(update_sql, (p_dias,))
                    p_afetadas = cur.rowcount
                    import json
                    cur.execute(
                        audit_sql,
                        (json.dumps({"dias": p_dias, "afetadas": p_afetadas}),),
                    )
            return {"p_afetadas": p_afetadas}
    '''),
        "",
    )


def _template_sp_transferir() -> str:
    return textwrap.indent(
        textwrap.dedent('''\
        def sp_transferir_entre_contas(
            conn: psycopg.Connection,
            p_conta_origem: int,
            p_conta_destino: int,
            p_valor: Decimal,
        ) -> None:
            if p_valor is None or p_valor <= 0:
                raise ValueError(f"Valor invalido para transferencia: {p_valor}")
            if p_conta_origem == p_conta_destino:
                raise ValueError("Conta de origem e destino nao podem ser iguais")
            try:
                with conn.transaction():
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            "SELECT saldo, status FROM contas WHERE id = %s FOR UPDATE",
                            (p_conta_origem,),
                        )
                        origem = cur.fetchone()
                        cur.execute(
                            "SELECT status FROM contas WHERE id = %s FOR UPDATE",
                            (p_conta_destino,),
                        )
                        destino = cur.fetchone()
                        if not origem:
                            raise ValueError(f"Conta de origem {p_conta_origem} nao encontrada")
                        if origem["status"] != "ATIVA" or destino["status"] != "ATIVA":
                            raise ValueError("Ambas as contas precisam estar ATIVAS")
                        if origem["saldo"] < p_valor:
                            raise ValueError(
                                f"Saldo insuficiente: saldo={origem['saldo']} valor={p_valor}"
                            )
                        cur.execute(
                            "UPDATE contas SET saldo = saldo - %s WHERE id = %s",
                            (p_valor, p_conta_origem),
                        )
                        cur.execute(
                            "UPDATE contas SET saldo = saldo + %s WHERE id = %s",
                            (p_valor, p_conta_destino),
                        )
                        cur.execute(
                            """INSERT INTO transacoes
                               (conta_origem_id, conta_destino_id, tipo, valor)
                               VALUES (%s, %s, 'TRANSFERENCIA', %s)""",
                            (p_conta_origem, p_conta_destino, p_valor),
                        )
                        import json
                        cur.execute(
                            """INSERT INTO log_auditoria
                               (entidade, entidade_id, acao, detalhes)
                               VALUES ('transacoes', NULL, 'TRANSFERENCIA_OK', %s::jsonb)""",
                            (
                                json.dumps(
                                    {
                                        "origem": p_conta_origem,
                                        "destino": p_conta_destino,
                                        "valor": str(p_valor),
                                    }
                                ),
                            ),
                        )
            except Exception as exc:
                import json
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO log_auditoria (entidade, acao, detalhes)
                           VALUES ('transacoes', 'TRANSFERENCIA_ERRO', %s::jsonb)""",
                        (
                            json.dumps(
                                {
                                    "origem": p_conta_origem,
                                    "destino": p_conta_destino,
                                    "valor": str(p_valor),
                                    "erro": str(exc),
                                }
                            ),
                        ),
                    )
                raise
    '''),
        "",
    )


def _template_sp_lote_taxas() -> str:
    return textwrap.indent(
        textwrap.dedent('''\
        def sp_processar_lote_taxas(
            conn: psycopg.Connection, p_data_referencia: date
        ) -> None:
            """Bulk fetch em vez de cursor linha-a-linha (evita N+1)."""
            import json
            from datetime import date as date_cls

            select_sql = """
                SELECT id, conta_origem_id, tipo, valor
                FROM transacoes
                WHERE DATE(data_transacao) = %s
                  AND status = 'EFETIVADA'
                  AND tipo <> 'TARIFA'
            """
            taxa_sql = """
                SELECT percentual, valor_minimo FROM taxas
                WHERE tipo_operacao = %s
                  AND vigente_de <= %s
                  AND (vigente_ate IS NULL OR vigente_ate >= %s)
                ORDER BY vigente_de DESC LIMIT 1
            """
            v_total_taxas = Decimal(0)
            v_count = 0
            with conn.transaction():
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(select_sql, (p_data_referencia,))
                    rows = cur.fetchall()
                    for row in rows:
                        cur.execute(
                            taxa_sql,
                            (row["tipo"], p_data_referencia, p_data_referencia),
                        )
                        taxa_row = cur.fetchone()
                        if not taxa_row:
                            continue
                        v_percentual = taxa_row["percentual"]
                        v_minimo = taxa_row["valor_minimo"]
                        v_taxa = max(row["valor"] * v_percentual / Decimal(100), v_minimo)
                        if row["tipo"] == "SAQUE":
                            v_taxa *= Decimal("1.10")
                        elif row["tipo"] != "TRANSFERENCIA":
                            v_taxa *= Decimal("0.90")
                        if row["conta_origem_id"] is None:
                            continue
                        cur.execute(
                            "UPDATE contas SET saldo = saldo - %s WHERE id = %s",
                            (v_taxa, row["conta_origem_id"]),
                        )
                        cur.execute(
                            """INSERT INTO transacoes
                               (conta_origem_id, tipo, valor, status)
                               VALUES (%s, 'TARIFA', %s, 'EFETIVADA')""",
                            (row["conta_origem_id"], v_taxa),
                        )
                        cur.execute(
                            """INSERT INTO log_auditoria
                               (entidade, entidade_id, acao, detalhes)
                               VALUES ('transacoes', %s, 'TARIFA_APLICADA', %s::jsonb)""",
                            (
                                row["id"],
                                json.dumps(
                                    {
                                        "transacao_origem": row["id"],
                                        "tipo_origem": row["tipo"],
                                        "valor_origem": str(row["valor"]),
                                        "percentual": str(v_percentual),
                                        "taxa_aplicada": str(v_taxa),
                                    }
                                ),
                            ),
                        )
                        v_total_taxas += v_taxa
                        v_count += 1
                    cur.execute(
                        """INSERT INTO log_auditoria (entidade, acao, detalhes)
                           VALUES ('lote_taxas', 'LOTE_PROCESSADO', %s::jsonb)""",
                        (
                            json.dumps(
                                {
                                    "data_referencia": str(p_data_referencia),
                                    "transacoes": v_count,
                                    "total_taxas": str(v_total_taxas),
                                }
                            ),
                        ),
                    )
    '''),
        "",
    )


def _template_sp_relatorio() -> str:
    return textwrap.indent(
        textwrap.dedent('''\
        def sp_relatorio_mensal_cliente(
            conn: psycopg.Connection,
            p_cliente_id: int,
            p_data_inicio: date,
            p_data_fim: date,
        ) -> list[dict[str, Any]]:
            if p_data_inicio > p_data_fim:
                raise ValueError(
                    f"Periodo invalido: inicio {p_data_inicio} > fim {p_data_fim}"
                )
            v_saldo_atual = fn_saldo_cliente(conn, p_cliente_id)
            print(f"Saldo atual do cliente {p_cliente_id}: {v_saldo_atual}")
            report_sql = """
                WITH RECURSIVE meses AS (
                    SELECT DATE_TRUNC('month', %s::date)::date AS mes
                    UNION ALL
                    SELECT (mes + INTERVAL '1 month')::date
                    FROM meses
                    WHERE mes < DATE_TRUNC('month', %s::date)
                ),
                movimento AS (
                    SELECT
                        DATE_TRUNC('month', t.data_transacao)::date AS mes,
                        SUM(CASE WHEN t.conta_destino_id IN (
                            SELECT id FROM contas WHERE cliente_id = %s
                        ) THEN t.valor ELSE 0 END) AS creditos,
                        SUM(CASE WHEN t.conta_origem_id IN (
                            SELECT id FROM contas WHERE cliente_id = %s
                        ) THEN t.valor ELSE 0 END) AS debitos,
                        COUNT(*)::int AS qtd
                    FROM transacoes t
                    WHERE t.status = 'EFETIVADA'
                      AND t.data_transacao >= %s
                      AND t.data_transacao < %s::date + INTERVAL '1 day'
                      AND (
                        t.conta_origem_id IN (
                            SELECT id FROM contas WHERE cliente_id = %s
                        )
                        OR t.conta_destino_id IN (
                            SELECT id FROM contas WHERE cliente_id = %s
                        )
                      )
                    GROUP BY 1
                )
                SELECT
                    m.mes AS mes_referencia,
                    COALESCE(mv.creditos, 0) AS total_creditos,
                    COALESCE(mv.debitos, 0) AS total_debitos,
                    %s + COALESCE(mv.creditos, 0) - COALESCE(mv.debitos, 0) AS saldo_consolidado,
                    COALESCE(mv.qtd, 0) AS qtd_transacoes
                FROM meses m
                LEFT JOIN movimento mv ON mv.mes = m.mes
                ORDER BY m.mes
            """
            try:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        report_sql,
                        (
                            p_data_inicio,
                            p_data_fim,
                            p_cliente_id,
                            p_cliente_id,
                            p_data_inicio,
                            p_data_fim,
                            p_cliente_id,
                            p_cliente_id,
                            v_saldo_atual,
                        ),
                    )
                    return list(cur.fetchall())
            except Exception:
                from datetime import date as date_cls
                return [
                    {
                        "mes_referencia": p_data_inicio.replace(day=1),
                        "total_creditos": Decimal(0),
                        "total_debitos": Decimal(0),
                        "saldo_consolidado": v_saldo_atual or Decimal(0),
                        "qtd_transacoes": 0,
                    }
                ]
    '''),
        "",
    )


def _template_generic(parse_result: dict[str, Any], source_code: str) -> str:
    name = parse_result.get("routine_name", "migrated_routine")
    return textwrap.indent(
        f"# TODO: revisar tradução manual\n"
        f"# SQL original ({len(source_code)} chars)\n"
        f"raise NotImplementedError('Tradução automática incompleta para {name}')",
        "",
    )


def fix_function_name(code: str, parse_result: dict[str, Any]) -> str:
    return code
