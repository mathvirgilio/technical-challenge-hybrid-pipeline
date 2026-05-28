from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection

from hybrid_pipeline.config import get_settings

INIT_SQL = """
CREATE TABLE IF NOT EXISTS modernization_history (
    id BIGSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL,
    generated_code TEXT,
    report JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('success', 'failure', 'partial')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS migration_metrics (
    id BIGSERIAL PRIMARY KEY,
    routine_name VARCHAR(200) NOT NULL,
    ast_parse_rate NUMERIC(5,4) NOT NULL,
    execution_status VARCHAR(20) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


@contextmanager
def get_connection() -> Iterator[Connection]:
    settings = get_settings()
    conn = psycopg.connect(settings.database_url, connect_timeout=2)
    try:
        yield conn
    finally:
        conn.close()


def init_database() -> None:
    with get_connection() as conn:
        conn.execute(INIT_SQL)
        conn.commit()
