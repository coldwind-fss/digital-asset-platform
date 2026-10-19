import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.config import MigrationSettings, Settings
from app.platform.db.target import (
    DatabaseTargetError,
    create_database_engine,
    create_engine_for_migration,
    parse_database_url,
    verify_database_identity,
)


def test_database_url_requires_exact_postgres_driver_and_expected_name() -> None:
    url = parse_database_url(
        "postgresql+psycopg://runtime:synthetic-secret@localhost:5432/digital_asset_platform",
        "digital_asset_platform",
    )
    assert url.database == "digital_asset_platform"


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://runtime:synthetic-secret@localhost:5432/legacy_accounts",
        "sqlite:///legacy.db",
        "not a database URL",
    ],
)
def test_database_target_guard_rejects_wrong_or_unsafe_url_without_echoing_it(database_url: str) -> None:
    with pytest.raises(DatabaseTargetError) as error:
        parse_database_url(database_url, "digital_asset_platform")
    assert "synthetic-secret" not in str(error.value)
    assert "legacy_accounts" not in str(error.value)


def test_database_configuration_requires_target_identity() -> None:
    with pytest.raises(ValueError, match="expected_database and instance_id"):
        Settings(database_url="postgresql+psycopg://runtime:placeholder@localhost/digital_asset_platform")


def test_migration_process_rejects_runtime_role() -> None:
    settings = MigrationSettings(
        app_env="test",
        migration_database_url="postgresql+psycopg://runtime:synthetic-secret@localhost:5432/digital_asset_platform",
        runtime_database_user="runtime",
        expected_database="digital_asset_platform",
        instance_id="digital-asset-platform-test-instance",
    )
    with pytest.raises(DatabaseTargetError) as error:
        create_engine_for_migration(settings)
    assert "synthetic-secret" not in str(error.value)


@pytest.mark.skipif(os.getenv("DAP_POSTGRES_TESTS") != "1", reason="requires the isolated CI PostgreSQL service")
def test_runtime_role_can_read_marker_but_cannot_run_ddl() -> None:
    settings = Settings.from_environment()
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            verify_database_identity(
                connection,
                expected_database=settings.expected_database or "",
                expected_instance_id=settings.instance_id or "",
                expected_environment=settings.app_env,
            )
            with pytest.raises(DBAPIError):
                connection.execute(text("CREATE TABLE digital_asset_platform_runtime_must_not_ddl (id integer)"))
                connection.commit()
            connection.rollback()
    finally:
        engine.dispose()
