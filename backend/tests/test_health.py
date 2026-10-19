from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_liveness_is_wrapped_and_carries_a_request_id() -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "ok"
    assert payload["error"] is None
    assert payload["meta"]["request_id"] == response.headers["x-request-id"]


def test_readiness_does_not_claim_unconfigured_database_is_ready() -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert payload["meta"]["request_id"] == response.headers["x-request-id"]


def test_resource_route_is_default_deny() -> None:
    response = client.get("/api/v1/resources", params={"type": "api_key"})

    assert response.status_code == 401
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == "AUTHENTICATION_REQUIRED"
