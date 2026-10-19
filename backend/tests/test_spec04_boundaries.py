from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.modules.bindings.api.schemas import BindingCreateRequest, ContactIdentityInput


def _client() -> TestClient:
    return TestClient(create_app(Settings(app_env="test", auth_provider="test")))


@pytest.mark.parametrize(
    ("path", "capability"),
    [
        ("/api/v1/people", "directory.read"),
        ("/api/v1/departments", "directory.read"),
        ("/api/v1/companies", "directory.read"),
        (f"/api/v1/resources/{uuid4()}/relations", "resource.read"),
        (f"/api/v1/resources/{uuid4()}/bindings", "binding.read"),
        ("/api/v1/change-cases", "governance.read"),
    ],
)
def test_spec04_routes_require_capability_and_then_report_missing_database(
    path: str,
    capability: str,
) -> None:
    client = _client()
    subject = str(uuid4())

    unauthenticated = client.get(path)
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    authenticated = client.get(
        path,
        headers={
            "X-DAP-Test-Subject": subject,
            "X-DAP-Test-Capabilities": capability,
        },
    )
    assert authenticated.status_code == 503
    assert authenticated.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


def test_binding_input_rejects_ambiguous_contact_sources() -> None:
    with pytest.raises(ValueError):
        BindingCreateRequest(
            expected_version=1,
            purpose="login",
            contact_identity_id=uuid4(),
            contact=ContactIdentityInput(
                kind="email",
                value="alias@example.com",
                ownership="company",
            ),
        )


def test_mailbox_contact_input_rejects_direct_custodian_mix() -> None:
    with pytest.raises(ValueError):
        ContactIdentityInput(
            kind="email",
            value="alias@example.com",
            ownership="company",
            mailbox_account_id=uuid4(),
            mailbox_association_role="alias",
            custodian_person_id=uuid4(),
        )


def test_governance_write_capability_reaches_database_dependency() -> None:
    client = _client()
    response = client.post(
        "/api/v1/change-cases",
        headers={
            "X-DAP-Test-Subject": str(uuid4()),
            "X-DAP-Test-Capabilities": "governance.write",
        },
        json={
            "case_type": "transfer",
            "reason": "负责人交接",
            "coordinator_person_id": str(uuid4()),
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
