from datetime import timedelta
from uuid import UUID,uuid4
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from test_local_identity import identity_env,DB_TESTS
from test_stage2 import post,created,resource
from app.platform.db.models import Resource,CredentialRef,SyncJob,MetricSnapshot,PrivateFile,PlatformConnection,Material,ChangeItem,ResourcePerson,AuditEvent
from app.modules.integrations.application.service import run_once
from app.modules.integrations.application.deepseek import parse_balances,AdapterError
from app.platform.db.commands import now

pytestmark=DB_TESTS


def attach(env,r,value='synthetic-private-value',purpose='attach'):
    stage=created(post(env.admin,f"/resources/{r['id']}/secret-stages",{'kind':'api_key','secret_value':value,'purpose':purpose}))
    result=created(post(env.admin,f"/resources/{r['id']}/credentials",{'kind':'api_key','expected_version':r['version'],'stage_token':stage['stage_token']}))
    return result['safe_result']['credential_id']


def prepare_flow(env,r,proposal):
    actor=created(env.admin.get('/api/v1/auth/session'))['person_id']
    case=created(post(env.admin,'/change-cases',{'case_type':'change','reason':'Synthetic change','coordinator_person_id':actor}))
    item=created(post(env.admin,f"/change-cases/{case['id']}/items",{'resource_id':r['id'],'proposal':proposal}))
    case=created(env.admin.get('/api/v1/change-cases/'+case['id']))
    created(post(env.admin,f"/change-cases/{case['id']}/actions/submit",{'expected_version':case['version']}))
    item=created(post(env.admin,f"/change-items/{item['id']}/actions/start",{'expected_version':item['version']}))
    evidence=created(post(env.admin,f"/resources/{r['id']}/materials",{'kind':'note','body':'Synthetic verified external operation result'}))
    item=created(post(env.admin,f"/change-items/{item['id']}/actions/record-execution",{'expected_version':item['version'],'evidence_ids':[evidence['id']],'non_secret_result':'External operation completed'}))
    return item,case


def test_credential_bound_stage_rotation_governance_and_independent_confirmation(identity_env):
    env=identity_env;r=resource(env,'api_key');other=resource(env,'api_key')
    stage=created(post(env.admin,f"/resources/{r['id']}/secret-stages",{'kind':'api_key','secret_value':'initial synthetic secret'}))
    wrong=post(env.admin,f"/resources/{other['id']}/credentials",{'kind':'api_key','expected_version':1,'stage_token':stage['stage_token']})
    assert wrong.status_code in {409,410},wrong.text
    credential=created(post(env.admin,f"/resources/{r['id']}/credentials",{'kind':'api_key','expected_version':1,'stage_token':stage['stage_token']}))['safe_result']['credential_id']
    current=created(env.admin.get('/api/v1/resources/'+r['id']))
    replacement=created(post(env.admin,f"/resources/{r['id']}/secret-stages",{'kind':'api_key','secret_value':'replacement synthetic secret','purpose':'replace'}))
    operation=created(post(env.admin,f'/credentials/{credential}/operations',{'expected_version':1,'action':'replace','stage_token':replacement['stage_token'],'reason':'Synthetic rotation'}))
    item,case=prepare_flow(env,current,{'action':'rotate_credential','credential_id':credential,'operation_id':operation['id']})
    assert post(env.admin,f"/change-items/{item['id']}/actions/confirm",{'expected_version':item['version'],'confirmation_note':'self'}).status_code==403
    reviewer,_=env.member('independent-reviewer','resource_manager',[{'kind':'resource','target_id':r['id'],'permission':'manage'}])
    completed=created(post(reviewer,f"/change-items/{item['id']}/actions/confirm",{'expected_version':item['version'],'confirmation_note':'Independent review'}))
    assert completed['status']=='completed'
    with Session(env.engine) as db:
        old=db.get(CredentialRef,UUID(credential));assert old.status=='superseded'
        new=db.scalar(select(CredentialRef).where(CredentialRef.resource_id==UUID(r['id']),CredentialRef.status=='saved'))
        assert b'replacement synthetic secret' not in new.ciphertext
        assert db.get(ChangeItem,UUID(item['id'])).execution_history


def test_worker_real_job_retry_preserves_last_good_snapshot_and_stale_configuration(identity_env):
    env=identity_env;r=resource(env,'api_key');credential=attach(env,r)
    connection=created(post(env.admin,'/platform-connections',{'resource_id':r['id'],'credential_id':credential,'provider':'deepseek','label':'Synthetic balance','scheduled':False}))
    job=created(post(env.admin,f"/platform-connections/{connection['id']}/actions/sync"))
    balances=parse_balances({'is_available':True,'balance_infos':[{'currency':'CNY','total_balance':'12.00','granted_balance':'2.00','topped_up_balance':'10.00'}]})
    def success(secret):assert secret=='synthetic-private-value';return balances
    assert run_once(env.engine,env.settings,fetcher=success)['status']=='succeeded'
    assert created(env.admin.get('/api/v1/metric-snapshots'))['pagination']['total']==1
    failed=created(post(env.admin,f"/platform-connections/{connection['id']}/actions/sync"))
    def failure(secret):raise AdapterError('PROVIDER_RATE_LIMITED',True,30)
    for attempt in range(3):
        with Session(env.engine) as db:
            row=db.get(SyncJob,UUID(failed['id']));row.available_at=now()-timedelta(seconds=1);db.commit()
        result=run_once(env.engine,env.settings,fetcher=failure)
        assert result['status']==('pending' if attempt<2 else 'failed')
    with Session(env.engine) as db:
        assert db.scalar(select(func.count()).select_from(MetricSnapshot))==1
        row=db.get(PlatformConnection,UUID(connection['id']));assert row.last_success_at and row.last_error_code=='PROVIDER_RATE_LIMITED'
    created(post(env.admin,f"/platform-connections/{connection['id']}/actions/sync"))
    def changed(secret):
        with Session(env.engine) as db:
            db.get(CredentialRef,UUID(credential)).version+=1;db.commit()
        return balances
    assert run_once(env.engine,env.settings,fetcher=changed)['status']=='failed'
    assert created(env.admin.get('/api/v1/metric-snapshots'))['pagination']['total']==1


def test_import_preview_atomic_commit_deduplication_and_scope_export(identity_env):
    env=identity_env
    batch=created(post(env.admin,'/imports/preview',{'type_code':'application','label':'Synthetic CSV','csv_content':'name,purpose\nApp One,Research\nApp Two,Operations\n'}))
    assert created(env.admin.get('/api/v1/resources'))['pagination']['total']==0
    key=str(uuid4());path=f"/imports/{batch['id']}/actions/commit";payload={'expected_version':1}
    result=created(post(env.admin,path,payload,key));again=created(post(env.admin,path,payload,key))
    assert result==again and len(result['results'])==2
    assert created(env.admin.get('/api/v1/resources'))['pagination']['total']==2
    duplicate=created(post(env.admin,'/imports/preview',{'type_code':'application','label':'Duplicate','csv_content':'name\nApp One\n'}))
    assert duplicate['results'][0]['status']=='duplicate_candidate'
    assert post(env.admin,f"/imports/{duplicate['id']}/actions/commit",{'expected_version':1}).status_code==409
    assert post(env.admin,'/imports/preview',{'type_code':'application','label':'Forbidden','csv_content':'name,password\nA,secret\n'}).status_code==422
    member,_=env.member()
    assert member.get('/api/v1/imports/'+batch['id']).status_code==404
    assert 'App One' not in member.get('/api/v1/exports/resources').text
    resource(env,name='=SUM(1+1)')
    assert "'=SUM(1+1)" in env.admin.get('/api/v1/exports/resources').text


def test_private_file_upload_download_replacement_end_and_cross_scope(identity_env):
    env=identity_env;r=resource(env)
    path='/api/v1/files';query={'resource_id':r['id'],'filename':'evidence.txt'}
    response=env.admin.post(path,params=query,content=b'Synthetic evidence',headers={'Content-Type':'application/octet-stream','Idempotency-Key':str(uuid4())})
    file=created(response)
    downloaded=env.admin.get(f"/api/v1/files/{file['id']}/content")
    assert downloaded.content==b'Synthetic evidence' and downloaded.headers['x-content-type-options']=='nosniff'
    member,_=env.member();assert member.get(f"/api/v1/files/{file['id']}/content").status_code==404
    material=created(post(env.admin,f"/resources/{r['id']}/materials",{'kind':'attachment','title':'Evidence','file_ref':file['id']}))
    query.update(replaces_file_id=file['id'],expected_version=1)
    new=created(env.admin.post(path,params=query,content=b'Updated evidence',headers={'Content-Type':'application/octet-stream','Idempotency-Key':str(uuid4())}))
    assert env.admin.get(f"/api/v1/files/{file['id']}/content").status_code==404
    with Session(env.engine) as db:assert Path(env.settings.private_file_root,db.get(PrivateFile,UUID(file['id'])).storage_key).is_file()
    created(post(env.admin,f"/files/{new['id']}/actions/end",{'expected_version':1,'reason':'Synthetic end'}))
    assert env.admin.get(f"/api/v1/files/{new['id']}/content").status_code==404
    query={'resource_id':r['id'],'filename':'../escape.txt'}
    assert env.admin.post(path,params=query,content=b'abc',headers={'Content-Type':'application/octet-stream','Idempotency-Key':str(uuid4())}).status_code==422


def test_governed_use_lifecycle_cancellation_and_immutable_facts(identity_env):
    env=identity_env;r=resource(env)
    reviewer,account=env.member('flow-reviewer','resource_manager',[{'kind':'resource','target_id':r['id'],'permission':'manage'}])
    item,case=prepare_flow(env,r,{'action':'grant_use','person_id':account['person_id']})
    done=created(post(reviewer,f"/change-items/{item['id']}/actions/confirm",{'expected_version':item['version'],'confirmation_note':'Reviewed actual access'}))
    assert done['status']=='completed'
    r=created(env.admin.get('/api/v1/resources/'+r['id']))
    item,case=prepare_flow(env,r,{'action':'disable_resource'})
    cancelled=created(post(env.admin,f"/change-items/{item['id']}/actions/request-cancellation",{'expected_version':item['version'],'reason':'External work reversed'}))
    assert cancelled['status']=='cancellation_requested'
    assert post(env.admin,f"/change-items/{item['id']}/actions/confirm-cancellation",{'expected_version':cancelled['version'],'reason':'self'}).status_code==403
    created(post(reviewer,f"/change-items/{item['id']}/actions/confirm-cancellation",{'expected_version':cancelled['version'],'reason':'Independently checked reversal'}))
    assert created(env.admin.get('/api/v1/resources/'+r['id']))['lifecycle']=='unknown'
