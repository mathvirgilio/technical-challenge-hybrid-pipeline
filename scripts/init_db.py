"""Inicializa tabelas no PostgreSQL."""

from hybrid_pipeline.persistence.db import init_database


def main() -> None:
    init_database()
    print("Database initialized (modernization_history, migration_metrics).")


if __name__ == "__main__":
    main()
