"""Módulo gerado a partir de PROCEDURE sp_atualizar_status_contas_inativas.
Estratégia: sqlalchemy_dml_with_python_validation.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row


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

