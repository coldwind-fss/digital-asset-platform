"""Fail-closed PostgreSQL target validation and identity checks."""

from __future__ import annotations

from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

from app.config import MigrationSettings, Settings


class DatabaseTargetError(RuntimeError):
    """Raised with safe text when a DB target is missing or mismatched."""


def parse_database_url(database_url: str, expected_database: str) -> URL:
    try:
        url = make_url(database_url)
    except Exception:
        raise DatabaseTargetError("Digital Asset Platform DATABASE_URL is invalid") from None

    if url.drivername != "postgresql+psycopg":
        raise DatabaseTargetError("Digital Asset Platform requires the PostgreSQL psycopg driver")
    if not url.database or url.database != expected_database:
        raise DatabaseTargetError("Digital Asset Platform database name does not match EXPECTED_DATABASE")
    if not url.username or not url.host:
        raise DatabaseTargetError("Digital Asset Platform database URL must specify a user and host")
    return url


def create_database_engine(settings: Settings) -> Engine:
    if not settings.database_url or not settings.expected_database:
        raise DatabaseTargetError("Digital Asset Platform database target configuration is incomplete")
    url = parse_database_url(settings.database_url, settings.expected_database)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        hide_parameters=True,
    )


def create_engine_for_migration(settings: MigrationSettings) -> Engine:
    url = parse_database_url(settings.migration_database_url, settings.expected_database)
    if url.username == settings.runtime_database_user:
        raise DatabaseTargetError("Digital Asset Platform runtime and migration database roles must be different")
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


def verify_database_name(connection: Connection, expected_database: str) -> None:
    try:
        actual_database = connection.execute(text("SELECT current_database()")).scalar_one()
    except SQLAlchemyError:
        raise DatabaseTargetError("Digital Asset Platform database target could not be verified") from None
    if actual_database != expected_database:
        raise DatabaseTargetError("Connected database does not match EXPECTED_DATABASE")


def verify_migration_target(connection: Connection, *, expected_database: str, expected_instance_id: str, expected_environment: str) -> None:
    """Check the marker BEFORE allowing Alembic to execute any DDL."""
    verify_database_name(connection, expected_database)
    tables = set(inspect(connection).get_table_names())
    if "instance_metadata" in tables:
        verify_database_identity(connection, expected_database=expected_database,
                                 expected_instance_id=expected_instance_id, expected_environment=expected_environment)
    elif tables:
        if tables != {"alembic_version"} or connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one():
            raise DatabaseTargetError("Migration target contains tables without a compatible instance marker")


def verify_database_identity(
    connection: Connection,
    *,
    expected_database: str,
    expected_instance_id: str,
    expected_environment: str,
) -> None:
    try:
        verify_database_name(connection, expected_database)

        if "instance_metadata" not in inspect(connection).get_table_names():
            raise DatabaseTargetError("Digital Asset Platform database schema is not migrated")
        row = connection.execute(
            text(
                "SELECT instance_id, environment, schema_family "
                "FROM instance_metadata WHERE singleton_key = 1"
            )
        ).mappings().one_or_none()
    except DatabaseTargetError:
        raise
    except SQLAlchemyError:
        raise DatabaseTargetError("Digital Asset Platform database identity could not be verified") from None

    if row is None:
        raise DatabaseTargetError("Digital Asset Platform database instance marker is missing")
    if (
        row["instance_id"] != expected_instance_id
        or row["environment"] != expected_environment
        or row["schema_family"] != "digital_asset_platform_resource"
    ):
        raise DatabaseTargetError("Digital Asset Platform database instance marker does not match configuration")


def verify_identity_schema(connection: Connection) -> None:
    """Runtime verification only; migrations must accept their older start point."""
    required = {
        "auth_account": {"id", "person_id", "password_hash", "role", "version"},
        "auth_session": {"token_hash", "authenticated_at", "revoked_at"},
        "auth_scope": {"account_id", "kind", "target_id", "permission"},
        "auth_action_token": {"token_hash", "used_at", "purpose"},
        "auth_throttle": {"key", "blocked_until"},
        "platform": {"id", "name"},
        "resource": {"created_by_person_id", "platform_id"},
        "credential_stage": {"created_by_person_id"},
        "change_case": {"created_by_person_id"},
        "department": {"version"},
    }
    try:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        if not required.keys() <= tables:
            raise DatabaseTargetError("Identity schema is not migrated; run the explicit migrator command")
        for table, names in required.items():
            if not names <= {c["name"] for c in inspector.get_columns(table)}:
                raise DatabaseTargetError("Identity schema is incompatible with this application")
    except SQLAlchemyError:
        raise DatabaseTargetError("Identity schema could not be verified") from None


def verify_runtime_schema(connection: Connection) -> None:
    """Refuse a partially migrated Stage 2 runtime without executing any DDL."""
    from app.platform.db.models import Base
    verify_identity_schema(connection)
    try:
        inspector=inspect(connection)
        tables=set(inspector.get_table_names())
        if not set(Base.metadata.tables)<=tables:raise DatabaseTargetError('Application schema is not migrated; run the explicit migrator')
        for name,table in Base.metadata.tables.items():
            if not set(table.c.keys())<={c['name'] for c in inspector.get_columns(name)}:raise DatabaseTargetError('Application schema is incompatible with this runtime')
    except SQLAlchemyError:raise DatabaseTargetError('Application schema could not be verified') from None
