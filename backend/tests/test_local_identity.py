from datetime import UTC, datetime, timedelta
from contextlib import ExitStack
from types import SimpleNamespace
import os
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app
from app.modules.identity_access.application.passwords import password_hash, password_matches
from app.platform.db.models import AuthAccount, AuthSession, AuthActionToken, AuditEvent, Base
from app.platform.db.target import verify_database_identity, verify_migration_target, DatabaseTargetError

PASSWORD = "Stage1-Test-Password-2026!"
ORIGIN = "http://127.0.0.1:5175"
BOOTSTRAP = "stage1-test-bootstrap-token-only-2026"
DB_TESTS = pytest.mark.skipif(os.getenv("DAP_STAGE1_POSTGRES_TESTS") != "1", reason="requires the explicitly isolated workspace test database")


def test_password_hash_is_salted_scrypt_and_rejects_wrong_or_malformed_values():
    first, second = password_hash(PASSWORD), password_hash(PASSWORD)
    assert first != second and PASSWORD not in first
    assert password_matches(PASSWORD, first)
    assert not password_matches("wrong", first)
    assert not password_matches(PASSWORD, "scrypt$999999999$8$3$bad$bad")
    assert not password_matches(PASSWORD, None)


def test_production_local_auth_requires_secure_cookie_and_test_identity_is_forbidden():
    base = dict(app_env="production", database_url="postgresql+psycopg://runtime:x@localhost/example", expected_database="example", instance_id="example", credential_master_key="eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=")
    with pytest.raises(ValueError):
        Settings(**base, auth_provider="local", auth_cookie_secure=False)
    with pytest.raises(ValueError):
        Settings(**base, auth_provider="test")
    assert Settings(**base, auth_provider="local", auth_cookie_secure=True)


@pytest.fixture
def identity_env(tmp_path):
    if os.getenv("DAP_STAGE1_POSTGRES_TESTS") != "1":
        pytest.skip("requires isolated workspace test database")
    settings = Settings.model_validate({**Settings.from_environment().model_dump(), "auth_provider":"local", "auth_bootstrap_token":BOOTSTRAP, "allowed_origins":(ORIGIN,), "auth_cookie_secure":False,"private_file_root":str(tmp_path/'private-files')})
    allowed_targets = {("digital_asset_platform_workspace_test", "digital-asset-platform-workspace-test"), ("digital_asset_platform_ci", "digital-asset-platform-ci-instance")}
    assert settings.app_env == "test" and (settings.expected_database, settings.instance_id) in allowed_targets
    engine = create_engine(os.environ["MIGRATOR_DATABASE_URL"],hide_parameters=True)
    with engine.connect() as connection:
        verify_database_identity(connection, expected_database=settings.expected_database, expected_instance_id=settings.instance_id, expected_environment="test")
        names = [n for n in Base.metadata.tables if n != "instance_metadata"]
        connection.execute(text("TRUNCATE " + ",".join('"'+n+'"' for n in names) + " CASCADE"))
        connection.commit()
    with ExitStack() as stack:
        def client():
            result = stack.enter_context(TestClient(create_app(settings),headers={"Origin":ORIGIN}))
            return result
        admin = client()
        response = admin.post("/api/v1/auth/bootstrap",json={"username":"stage-admin","display_name":"阶段一管理员","password":PASSWORD,"bootstrap_token":BOOTSTRAP})
        assert response.status_code == 201, response.text
        admin.headers["X-CSRF-Token"] = response.json()["data"]["csrf_token"]
        def member(username="stage-member",role="member",scopes=None,department_id=None):
            response = admin.post("/api/v1/admin/accounts",json={"username":username,"display_name":username,"role":role,"scopes":scopes or [],"department_id":department_id})
            assert response.status_code==201,response.text
            data=response.json()["data"]
            other=client()
            activated=other.post("/api/v1/auth/activate",json={"action_token":data["action_token"],"new_password":PASSWORD})
            assert activated.status_code==200,activated.text
            logged=other.post("/api/v1/auth/login",json={"username":username,"password":PASSWORD})
            assert logged.status_code==200,logged.text
            other.headers["X-CSRF-Token"]=logged.json()["data"]["csrf_token"]
            return other,data["account"]
        yield SimpleNamespace(admin=admin,client=client,member=member,engine=engine,settings=settings,bootstrap_response=response)
    engine.dispose()


@DB_TESTS
def test_bootstrap_cookie_csrf_and_token_storage(identity_env):
    env=identity_env
    response=env.bootstrap_response
    assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=lax" in response.headers["set-cookie"]
    assert response.headers["cache-control"]=="no-store"
    assert env.admin.get("/api/v1/auth/session").status_code==200
    repeated=env.admin.post("/api/v1/auth/bootstrap",json={"username":"another-admin","display_name":"another","password":PASSWORD,"bootstrap_token":BOOTSTRAP})
    assert repeated.status_code==409
    assert env.admin.post("/api/v1/admin/accounts",json={"username":"a-user","display_name":"User"},headers={"X-CSRF-Token":"bad"}).status_code==403
    assert env.admin.post("/api/v1/admin/accounts",json={"username":"a-user","display_name":"User"},headers={"Origin":"https://untrusted.example.test"}).status_code==403
    assert env.admin.get("/api/v1/resources",headers={"X-DAP-Test-Subject":"11111111-1111-4111-8111-111111111111","X-DAP-Test-Capabilities":"identity.manage"}).status_code==403
    with Session(env.engine) as session:
        account=session.scalar(select(AuthAccount))
        stored=session.scalar(select(AuthSession))
        assert account.password_hash.startswith("scrypt$") and PASSWORD not in account.password_hash
        assert stored.token_hash != env.admin.cookies.get(env.settings.auth_cookie_name).encode()
        assert session.scalar(select(AuditEvent.id).where(AuditEvent.event_type=="auth.bootstrap"))


@DB_TESTS
def test_real_member_cannot_read_or_modify_another_scope(identity_env):
    env=identity_env
    hidden=env.admin.post("/api/v1/resources",json={"name":"Private admin resource","type_code":"application"})
    assert hidden.status_code==201,hidden.text
    hidden_id=hidden.json()["data"]["id"]
    member,_=env.member()
    assert member.get("/api/v1/admin/accounts").status_code==403
    assert member.get("/api/v1/resources").json()["data"]["pagination"]["total"]==0
    assert member.get("/api/v1/resources/"+hidden_id).status_code==404
    assert member.patch("/api/v1/resources/"+hidden_id,json={"expected_version":1,"changes":{"name":"illegal"}}).status_code in {403,404}
    linked=member.post("/api/v1/resources",json={"name":"Invalid reference","type_code":"application","relations":[{"target_id":hidden_id,"relation_type":"uses"}]})
    assert linked.status_code==404,linked.text
    own=member.post("/api/v1/resources",json={"name":"Own resource","type_code":"application"})
    assert own.status_code==201,own.text
    body=member.get("/api/v1/resources").json()["data"]
    assert body["pagination"]["total"]==1 and body["items"][0]["name"]=="Own resource"
    assert env.admin.get("/api/v1/resources").json()["data"]["pagination"]["total"]==2
    assert own.json()["data"]["owner"] is None


@DB_TESTS
def test_read_scope_does_not_enable_writes_and_admin_has_no_implicit_secret_view(identity_env):
    env=identity_env
    created=env.admin.post("/api/v1/resources",json={"name":"Read-only object","type_code":"application"}).json()["data"]
    manager,_=env.member("stage-manager","resource_manager",[{"kind":"resource","target_id":created["id"],"permission":"read"}])
    assert manager.get("/api/v1/resources").json()["data"]["pagination"]["total"]==1
    result=manager.patch("/api/v1/resources/"+created["id"],json={"expected_version":created["version"],"changes":{"name":"No write"}})
    assert result.status_code==403,result.text
    assert env.admin.get("/api/v1/resources/"+created["id"]).json()["data"]["name"]=="Read-only object"
    assert "credential.read" not in env.admin.get("/api/v1/auth/session").json()["data"]["capabilities"]


@DB_TESTS
def test_read_only_resource_scope_cannot_change_or_submit_its_governance_case(identity_env):
    env = identity_env
    resource = env.admin.post("/api/v1/resources", json={"name":"Governance scope fixture", "type_code":"application"}).json()["data"]
    manager, account = env.member("case-read-manager", "resource_manager", [{"kind":"resource", "target_id":resource["id"], "permission":"read"}])
    admin_person = env.admin.get("/api/v1/auth/session").json()["data"]["person_id"]
    case = env.admin.post("/api/v1/change-cases", json={"case_type":"transfer", "reason":"Synthetic scope test", "coordinator_person_id":admin_person}).json()["data"]
    added = env.admin.post("/api/v1/change-cases/"+case["id"]+"/items", json={"resource_id":resource["id"], "proposal":{"action":"change_owner", "to_person_id":account["person_id"]}})
    assert added.status_code == 201, added.text
    path = "/api/v1/change-cases/"+case["id"]
    visible = manager.get(path)
    assert visible.status_code == 200, visible.text
    version = visible.json()["data"]["version"]
    assert manager.patch(path, json={"expected_version":version,"reason":"Illegal edit"}).status_code == 403
    assert manager.post(path+"/actions/submit", json={"expected_version":version}).status_code == 403
    assert env.admin.get(path).json()["data"]["status"] == "draft"


@DB_TESTS
def test_activation_single_use_and_deactivation_revokes_existing_session(identity_env):
    env=identity_env
    member,account=env.member()
    assert member.get("/api/v1/auth/session").status_code==200
    result=env.admin.patch("/api/v1/admin/accounts/"+account["id"],json={"expected_version":2,"status":"inactive"})
    assert result.status_code==200,result.text
    assert member.get("/api/v1/auth/session").status_code==401
    assert member.post("/api/v1/auth/login",json={"username":account["username"],"password":PASSWORD}).status_code==401
    assert env.admin.post("/api/v1/admin/accounts/"+account["id"]+"/recovery-token").status_code==403


@DB_TESTS
def test_recovery_token_consumption_and_old_sessions_end(identity_env):
    env=identity_env
    member,account=env.member()
    token=env.admin.post("/api/v1/admin/accounts/"+account["id"]+"/recovery-token").json()["data"]["action_token"]
    assert member.get("/api/v1/auth/session").status_code==401
    anonymous=env.client()
    replacement="Replacement-Stage1-Password!"
    result=anonymous.post("/api/v1/auth/activate",json={"action_token":token,"new_password":replacement})
    assert result.status_code==200,result.text
    assert anonymous.post("/api/v1/auth/activate",json={"action_token":token,"new_password":replacement}).status_code==410
    assert anonymous.post("/api/v1/auth/login",json={"username":account["username"],"password":PASSWORD}).status_code==401
    assert anonymous.post("/api/v1/auth/login",json={"username":account["username"],"password":replacement}).status_code==200
    with Session(env.engine) as session:
        assert all(token.encode()!=row.token_hash for row in session.scalars(select(AuthActionToken)))


@DB_TESTS
def test_staged_secret_is_creator_bound_and_read_grant_requires_recent_auth(identity_env):
    env = identity_env
    resource = env.admin.post("/api/v1/resources", json={"name":"Credential scope fixture", "type_code":"platform_account"}).json()["data"]
    manager, _ = env.member("secret-manager", "resource_manager", [{"kind":"resource", "target_id":resource["id"], "permission":"manage"}])
    staged = env.admin.post("/api/v1/secret-stages", json={"kind":"password", "secret_value":"Synthetic-Secret-For-Stage1"})
    assert staged.status_code == 201, staged.text
    payload = {"expected_version":resource["version"], "kind":"password", "stage_token":staged.json()["data"]["stage_token"]}
    assert manager.post("/api/v1/resources/"+resource["id"]+"/credentials", json=payload).status_code == 410
    attached = env.admin.post("/api/v1/resources/"+resource["id"]+"/credentials", json=payload)
    assert attached.status_code == 202, attached.text
    credential_id = attached.json()["data"]["safe_result"]["credential_id"]
    member, account = env.member("secret-reader", scopes=[{"kind":"resource", "target_id":resource["id"], "permission":"read"}])
    reveal_path = "/api/v1/credentials/"+credential_id+"/actions/reveal"
    assert env.admin.post(reveal_path, json={"reason":"No implicit administrator access"}).status_code == 403
    assert member.post(reveal_path, json={"reason":"No grant"}).status_code == 403
    granted = env.admin.post("/api/v1/credentials/"+credential_id+"/grants", json={"expected_version":1,"person_id":account["person_id"],"capability":"view","valid_to":(datetime.now(UTC)+timedelta(hours=1)).isoformat(),"reason":"Stage1 synthetic read-only grant"})
    assert granted.status_code == 201, granted.text
    revealed = member.post(reveal_path, json={"reason":"Authorized read-only access"})
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["data"]["secret_value"] == "Synthetic-Secret-For-Stage1"
    assert revealed.headers["cache-control"] == "no-store"
    with Session(env.engine) as session:
        session.execute(update(AuthSession).where(AuthSession.account_id==UUID(account["id"])).values(authenticated_at=datetime.now(UTC)-timedelta(minutes=16)))
        session.commit()
        assert session.scalar(select(AuditEvent.id).where(AuditEvent.event_type=="credential_revealed"))
    expired = member.post(reveal_path, json={"reason":"Too old"})
    assert expired.status_code == 403 and expired.json()["error"]["code"] == "REAUTHENTICATION_REQUIRED"
    assert member.post("/api/v1/auth/reauthenticate", json={"password":PASSWORD}).status_code == 200
    assert member.post(reveal_path, json={"reason":"Reauthenticated"}).status_code == 200


@DB_TESTS
def test_last_administrator_version_conflicts_and_department_cycles(identity_env):
    env=identity_env
    account=env.admin.get("/api/v1/admin/accounts").json()["data"]["items"][0]
    assert env.admin.patch("/api/v1/admin/accounts/"+account["id"],json={"expected_version":account["version"],"status":"inactive"}).status_code==409
    assert env.admin.patch("/api/v1/admin/accounts/"+account["id"],json={"expected_version":999,"display_name":"stale"}).status_code==409
    first=env.admin.post("/api/v1/admin/departments",json={"name":"First"})
    assert first.status_code==201,first.text
    department=first.json()["data"]
    second=env.admin.post("/api/v1/admin/departments",json={"name":"Second","parent_id":department["id"]}).json()["data"]
    assert env.admin.patch("/api/v1/admin/departments/"+department["id"],json={"expected_version":1,"parent_id":second["id"]}).status_code==422
    assert env.admin.patch("/api/v1/admin/departments/"+department["id"],json={"expected_version":1,"status":"inactive"}).status_code==409


@DB_TESTS
def test_login_rate_limit_expiry_password_change_and_logout(identity_env):
    env=identity_env
    fresh=env.client()
    for _ in range(5):
        assert fresh.post("/api/v1/auth/login",json={"username":"not-a-user","password":"wrong"}).status_code==401
    assert fresh.post("/api/v1/auth/login",json={"username":"not-a-user","password":"wrong"}).status_code==429
    member,account=env.member()
    old_cookie=member.cookies.get(env.settings.auth_cookie_name)
    changed=member.post("/api/v1/auth/change-password",json={"current_password":PASSWORD,"new_password":"Changed-Stage1-Password!"})
    assert changed.status_code==200,changed.text
    replay=env.client()
    replay.cookies.set(env.settings.auth_cookie_name,old_cookie)
    assert replay.get("/api/v1/auth/session").status_code==401
    login=replay.post("/api/v1/auth/login",json={"username":account["username"],"password":"Changed-Stage1-Password!"})
    replay.headers["X-CSRF-Token"]=login.json()["data"]["csrf_token"]
    assert replay.post("/api/v1/auth/logout").status_code==200
    assert replay.get("/api/v1/auth/session").status_code==401
    with Session(env.engine) as session:
        session.execute(update(AuthSession).values(last_seen_at=datetime.now(UTC)-timedelta(hours=2)))
        session.commit()
    assert env.admin.get("/api/v1/auth/session").status_code==401


@DB_TESTS
def test_migration_guard_and_runtime_ddl_boundary(identity_env):
    env=identity_env
    with env.engine.connect() as connection:
        before=connection.execute(text("select version_num from alembic_version")).scalar_one()
        with pytest.raises(DatabaseTargetError):
            verify_migration_target(connection,expected_database=env.settings.expected_database,expected_instance_id="wrong-marker",expected_environment="test")
        assert connection.execute(text("select version_num from alembic_version")).scalar_one()==before
    engine=create_engine(env.settings.database_url,hide_parameters=True)
    with engine.connect() as connection:
        with pytest.raises(Exception):
            connection.execute(text("CREATE TABLE forbidden_runtime_ddl(id integer)"))
        connection.rollback()
    engine.dispose()
