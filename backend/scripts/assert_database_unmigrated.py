from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy import inspect

from app.config import MigrationSettings
from app.platform.db.target import create_engine_for_migration, parse_database_url, verify_database_name


def main() -> int:
    settings = MigrationSettings.from_environment()
    verification_url = os.getenv("VERIFY_DATABASE_URL")
    if verification_url:
        engine = create_engine(
            parse_database_url(verification_url, settings.expected_database),
            pool_pre_ping=True,
            hide_parameters=True,
        )
    else:
        engine = create_engine_for_migration(settings)
    try:
        with engine.connect() as connection:
            verify_database_name(connection, settings.expected_database)
            names = set(inspect(connection).get_table_names())
            if names & {"alembic_version", "instance_metadata"}:
                raise SystemExit("Rejected migration created Digital Asset Platform schema objects")
    finally:
        engine.dispose()
    print("Rejected migration left the database schema unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
