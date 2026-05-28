"""Módulo gerado a partir de FUNCTION fn_saldo_cliente.
Estratégia: python_orchestration_sql_queries.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row


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

