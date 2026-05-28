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
