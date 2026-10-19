import base64
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.modules.credentials.api.schemas import CredentialAttachRequest
from app.modules.credentials.application.crypto import decrypt_secret, encrypt_secret
from app.modules.credentials.application.service import attach_credential
from app.platform.db.models import CredentialRef, CredentialStage, Resource
from app.platform.http.errors import ApiException


def _settings() -> Settings:
    return Settings(
        app_env="test",
        auth_provider="test",
        credential_master_key=base64.urlsafe_b64encode(b"local-test-master-key-32-bytes!!").decode("ascii"),
    )


def test_application_managed_credential_encryption_round_trips_without_plaintext_storage() -> None:
    settings = _settings()
    encrypted = encrypt_secret(settings, "synthetic-secret", associated_data=b"credential:test")

    assert encrypted.ciphertext != b"synthetic-secret"
    assert b"synthetic-secret" not in encrypted.ciphertext
    assert decrypt_secret(
        settings,
        ciphertext=encrypted.ciphertext,
        nonce=encrypted.nonce,
        key_version=encrypted.key_version,
        associated_data=b"credential:test",
    ) == "synthetic-secret"


def test_application_managed_credential_encryption_rejects_wrong_associated_data() -> None:
    settings = _settings()
    encrypted = encrypt_secret(settings, "synthetic-secret", associated_data=b"credential:test")

    with pytest.raises(ApiException) as error:
        decrypt_secret(
            settings,
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
            key_version=encrypted.key_version,
            associated_data=b"credential:other",
        )

    assert error.value.code == "DEPENDENCY_UNAVAILABLE"


def test_credential_service_binds_ciphertext_to_pre_flush_record_ids() -> None:
    settings = _settings()
    resource_id = uuid4()
    stage = CredentialStage(
        id=uuid4(),
        token_hash=b"stage-token-hash",
        kind="password",
        ciphertext=b"",
        nonce=b"",
        key_version="key-1",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    stage_token = "stage-token-01234567890123456789"
    stage.token_hash = hashlib.sha256(stage_token.encode("utf-8")).digest()
    stage_encrypted = encrypt_secret(
        settings,
        "synthetic-secret",
        associated_data=f"credential-stage:{stage.id}".encode("utf-8"),
    )
    stage.ciphertext = stage_encrypted.ciphertext
    stage.nonce = stage_encrypted.nonce
    resource = Resource(
        id=resource_id,
        code="unit-resource",
        name="Unit resource",
        type_code="platform_account",
        version=1,
        archived_at=None,
    )
    session = Mock()
    session.get.return_value = resource
    session.info = {}
    stage.purpose='attach'
    session.scalar.side_effect = [resource, stage, None]

    credential_id = attach_credential(
        session,
        settings,
        resource_id,
        CredentialAttachRequest(expected_version=1, stage_token=stage_token, kind="password"),
        actor_id=uuid4(),
        request_id=uuid4(),
    )

    credential = next(item for item in (call.args[0] for call in session.add.call_args_list) if isinstance(item, CredentialRef))
    assert credential.id == credential_id
    assert decrypt_secret(
        settings,
        ciphertext=credential.ciphertext or b"",
        nonce=credential.nonce or b"",
        key_version=credential.key_version or "",
        associated_data=f"credential:{credential.id}".encode("utf-8"),
    ) == "synthetic-secret"


def test_credential_routes_keep_default_deny_and_database_dependency_order() -> None:
    client = TestClient(create_app(_settings()))
    unauthenticated = client.post(
        "/api/v1/secret-stages",
        json={"kind": "password", "secret_value": "synthetic-secret"},
    )
    assert unauthenticated.status_code == 401

    authenticated = client.post(
        "/api/v1/secret-stages",
        headers={
            "X-DAP-Test-Subject": str(uuid4()),
            "X-DAP-Test-Capabilities": "credential.write",
        },
        json={"kind": "password", "secret_value": "synthetic-secret"},
    )
    assert authenticated.status_code == 503
    assert authenticated.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"

    materials = client.get(
        f"/api/v1/resources/{uuid4()}/materials",
        headers={
            "X-DAP-Test-Subject": str(uuid4()),
            "X-DAP-Test-Capabilities": "materials.read",
        },
    )
    assert materials.status_code == 503
    assert materials.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
