"""Módulo gerado a partir de PROCEDURE sp_processar_lote_taxas.
Estratégia: hybrid_bulk_python.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row


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

