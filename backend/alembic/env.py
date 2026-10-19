from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy.exc import SQLAlchemyError

from app.config import MigrationSettings
from app.platform.db.models import Base
from app.platform.db.target import (
    create_engine_for_migration,
    verify_database_identity,
    verify_migration_target,
)


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    raise RuntimeError("Offline migrations are disabled because Digital Asset Platform must verify the live target first")


def run_migrations_online() -> None:
    migration_settings = MigrationSettings.from_environment()
    config.attributes["instance_id"] = migration_settings.instance_id
    config.attributes["environment"] = migration_settings.app_env

    engine = create_engine_for_migration(migration_settings)
    try:
        with engine.connect() as connection:
            verify_migration_target(connection, expected_database=migration_settings.expected_database,
                expected_instance_id=migration_settings.instance_id, expected_environment=migration_settings.app_env)
            connection.commit()
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                transaction_per_migration=True,
            )
            with context.begin_transaction():
                context.run_migrations()

            verify_database_identity(
                connection,
                expected_database=migration_settings.expected_database,
                expected_instance_id=migration_settings.instance_id,
                expected_environment=migration_settings.app_env,
            )
    except SQLAlchemyError:
        raise RuntimeError("Digital Asset Platform PostgreSQL migration failed; inspect the safe migration logs") from None
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
