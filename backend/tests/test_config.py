import base64

import pytest

from app.config import Settings


def test_development_configuration_does_not_require_an_implicit_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("EXPECTED_DATABASE", raising=False)
    monkeypatch.delenv("INSTANCE_ID", raising=False)

    settings = Settings.from_environment({"APP_ENV": "development", "AUTH_PROVIDER": "disabled"})

    assert settings.app_env == "development"
    assert settings.database_url is None
    assert settings.expected_database is None
    assert settings.instance_id is None


def test_explicit_database_configuration_requires_current_target_identity() -> None:
    settings = Settings.from_environment(
        {
            "APP_ENV": "development",
            "DATABASE_URL": "postgresql+psycopg://runtime:synthetic-secret@localhost:5432/digital_asset_platform",
            "EXPECTED_DATABASE": "digital_asset_platform",
            "INSTANCE_ID": "digital-asset-platform-local-test",
        }
    )

    assert settings.database_url is not None
    assert settings.expected_database == "digital_asset_platform"
    assert settings.instance_id == "digital-asset-platform-local-test"


def test_invalid_configuration_errors_do_not_echo_database_credentials() -> None:
    with pytest.raises(RuntimeError) as error:
        Settings.from_environment(
            {
                "APP_ENV": "development",
                "DATABASE_URL": "postgresql+psycopg://runtime:synthetic-secret@localhost:5432/digital_asset_platform",
                "EXPECTED_DATABASE": "digital_asset_platform",
                "INSTANCE_ID": "",
            }
        )

    assert "synthetic-secret" not in str(error.value)
    assert "DATABASE_URL" not in str(error.value)


def test_application_credential_key_requires_32_decoded_bytes() -> None:
    key = base64.urlsafe_b64encode(b"local-test-master-key-32-bytes!!").decode("ascii")
    settings = Settings.from_environment({"APP_ENV": "test", "CREDENTIAL_MASTER_KEY": key})
    assert settings.credential_master_key == key

    with pytest.raises(RuntimeError) as error:
        Settings.from_environment({"APP_ENV": "test", "CREDENTIAL_MASTER_KEY": "too-short"})
    assert "credential_master_key" in str(error.value)
