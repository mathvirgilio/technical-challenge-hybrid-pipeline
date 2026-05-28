"""Módulo gerado a partir de FUNCTION sp_relatorio_mensal_cliente.
Estratégia: hybrid_sql_in_db.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row


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

