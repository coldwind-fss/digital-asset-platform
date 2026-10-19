from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.modules.resources.api.schemas import ResourceCreateRequest
from app.modules.resources.domain.rules import ResourceRuleError, validate_attributes


def test_explicit_test_identity_reaches_database_dependency() -> None:
    client = TestClient(create_app(Settings(app_env="test", auth_provider="test")))
    response = client.get(
        "/api/v1/resources",
        headers={
            "X-DAP-Test-Subject": str(uuid4()),
            "X-DAP-Test-Capabilities": "resource.read",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


def test_test_identity_cannot_grant_unlisted_capability() -> None:
    client = TestClient(create_app(Settings(app_env="test", auth_provider="test")))
    response = client.get(
        "/api/v1/resources",
        headers={
            "X-DAP-Test-Subject": str(uuid4()),
            "X-DAP-Test-Capabilities": "admin.resource.read",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_resource_create_dto_accepts_unknown_metadata_but_not_unknown_type_attributes() -> None:
    payload = ResourceCreateRequest(name="  API key  ", type_code="api_key", attributes={"external_key_id": "public-id"})
    assert payload.name == "API key"

    try:
        validate_attributes("api_key", {"secret_value": "never-store"})
    except ResourceRuleError as error:
        assert error.field == "attributes"
    else:
        raise AssertionError("secret attributes must be rejected")


def test_subscription_budget_rules_preserve_original_currency_facts() -> None:
    attributes = {
        "budgets": [
            {"amount": "20.00", "currency": "USD", "period": "month", "meaning": "seat"},
            {"amount": "140.00", "currency": "RMB", "period": "year", "meaning": "annual"},
        ]
    }

    assert validate_attributes("service_subscription", attributes) == attributes
