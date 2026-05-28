from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from hybrid_pipeline.persistence.db import get_connection


class ModernizationRepository:
    def save(
        self,
        source_code: str,
        generated_code: str | None,
        report: dict[str, Any],
        status: str,
    ) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO modernization_history
                        (source_code, generated_code, report, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (source_code, generated_code, Jsonb(report), status),
                )
                row = cur.fetchone()
                conn.commit()
                return int(row[0])

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, status, created_at,
                           LEFT(source_code, 80) AS source_preview
                    FROM modernization_history
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    def save_metric(self, routine_name: str, ast_parse_rate: float, execution_status: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO migration_metrics
                        (routine_name, ast_parse_rate, execution_status)
                    VALUES (%s, %s, %s)
                    """,
                    (routine_name, ast_parse_rate, execution_status),
                )
                conn.commit()
