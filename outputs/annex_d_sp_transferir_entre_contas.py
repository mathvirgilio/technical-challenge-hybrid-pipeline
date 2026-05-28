"""Módulo gerado a partir de PROCEDURE sp_transferir_entre_contas.
Estratégia: sqlalchemy_dml_with_python_validation.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row


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

