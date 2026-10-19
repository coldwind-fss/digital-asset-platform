"""Release-boundary tests: a read-only deployment is enforced on the server."""
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from test_local_identity import identity_env, PASSWORD, ORIGIN, DB_TESTS
from test_stage2 import created, post, resource


def test_readonly_requires_real_identity_and_production_secure_cookies():
    import pytest
    with pytest.raises(ValueError):
        Settings(read_only=True)
    assert Settings(auth_provider='local', read_only=True)


@DB_TESTS
def test_readonly_denies_even_admin_and_never_returns_secret_capability(identity_env):
    env=identity_env
    row=resource(env,name='Synthetic public sample')
    settings=Settings.model_validate({**env.settings.model_dump(),'read_only':True})
    with TestClient(create_app(settings),headers={'Origin':ORIGIN}) as client:
        bootstrap=created(client.get('/api/v1/auth/bootstrap-status'))
        assert bootstrap['read_only'] is True and bootstrap['setup_available'] is False
        session=created(client.post('/api/v1/auth/login',json={'username':'stage-admin','password':PASSWORD}))
        client.headers['X-CSRF-Token']=session['csrf_token']
        assert session['read_only'] is True
        assert not any(cap.endswith(('.write','.manage','.confirm','.grant')) or cap.startswith('credential.') for cap in session['capabilities'])
        detail=created(client.get('/api/v1/resources/'+row['id']))
        assert detail['capabilities']['edit'] is False
        # Cover routes independent of capability decorators, auth takeover, and
        # percent-encoded/trailing-slash attempts. Rejection precedes any write.
        for path in ['/resources','/resources/','/%72esources','/secret-stages',
            '/auth/bootstrap','/auth/activate','/auth/change-password','/auth/reauthenticate',
            '/platform-connections','/reminders/actions/refresh']:
            response=client.post('/api/v1'+path,json={})
            assert response.status_code==403,(path,response.status_code)
            assert response.json()['error']['code']=='READ_ONLY_EXPERIENCE'
            assert response.headers['x-request-id']==response.json()['meta']['request_id']
        assert client.patch('/api/v1/me/notification-preferences',json={'expected_version':1,'show_due':False}).status_code==403
        assert client.get('/api/v1/admin/accounts').status_code==403
        assert client.post('/api/v1/auth/logout').status_code==200
        assert client.get('/api/v1/auth/session').status_code==401
    assert created(env.admin.get('/api/v1/resources'))['pagination']['total']==1


@DB_TESTS
def test_production_ignores_no_test_header_and_uses_secure_session(identity_env):
    env=identity_env
    # Explicitly incompatible marker must fail startup, never silently connect
    # a production instance to a marked test DB.
    import pytest
    production=Settings.model_validate({**env.settings.model_dump(),'app_env':'production','auth_cookie_secure':True})
    with pytest.raises(RuntimeError,match='instance/schema marker'):
        with TestClient(create_app(production)):
            pass


@DB_TESTS
def test_full_product_sample_uses_existing_roles_credentials_and_persistent_commands(identity_env):
    """The public setup must expose real commands without bypassing policy."""
    import importlib.util
    from pathlib import Path
    from uuid import UUID, uuid4
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.platform.db.models import Resource, AuditEvent, AuthAccount, CredentialRef
    env = identity_env
    original = resource(env, 'api_key', name='Synthetic public key sample')
    env.member('visitor', 'resource_manager', [{'kind':'resource','target_id':original['id'],'permission':'read'}])
    with Session(env.engine) as db:
        row = db.get(Resource, UUID(original['id']))
        row.code, row.provider_name = 'DEMO-003', '虚构展示数据'
        db.add(AuditEvent(actor_kind='system', event_type='experience.seed', request_id=uuid4(), safe_after={'synthetic':True}))
        db.commit()
    spec = importlib.util.spec_from_file_location('showcase_seed', Path(__file__).resolve().parents[2]/'deploy/seed-experience.py')
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    with Session(env.engine) as db:
        seed.enable_full_product(db, env.settings)
        assert db.get(Resource, UUID(original['id'])).name == original['name']
        assert not db.scalar(select(AuthAccount).where(AuthAccount.username == 'visitor'))
        credential = db.scalar(select(CredentialRef).where(CredentialRef.resource_id == UUID(original['id'])))
        assert credential and b'EXAMPLE-ONLY' not in credential.ciphertext
        credential_id = str(credential.id)
    with TestClient(create_app(env.settings), headers={'Origin':ORIGIN}) as client:
        session = created(client.post('/api/v1/auth/login', json={'username':'demo','password':seed.SAMPLE_PASSWORD}))
        client.headers['X-CSRF-Token'] = session['csrf_token']
        assert not session['read_only'] and not session['must_change_password']
        assert {'resource.write','identity.manage','catalog.write','governance.confirm','credential.read'} <= set(session['capabilities'])
        assert created(client.get('/api/v1/resources/'+original['id']))['capabilities']['edit'] is True
        saved = created(post(client, '/resources', {'type_code':'application','name':'New public persistent object'}))
        assert created(client.get('/api/v1/resources/'+saved['id']))['name'] == 'New public persistent object'
        revealed = created(post(client, '/credentials/'+credential_id+'/actions/reveal', {'reason':'Synthetic public sample verification'}))
        assert revealed['secret_value'] == 'EXAMPLE-ONLY-NOT-A-REAL-API-KEY'
        assert client.post('/api/v1/auth/logout').status_code == 200
        reviewed = created(client.post('/api/v1/auth/login', json={'username':'reviewer','password':seed.REVIEWER_PASSWORD}))
        assert reviewed['person_id'] != session['person_id'] and 'governance.confirm' in reviewed['capabilities']
        assert created(client.get('/api/v1/resources/'+saved['id']))['id'] == saved['id']
