from datetime import timedelta
from uuid import UUID,uuid4
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from test_local_identity import identity_env,DB_TESTS
from test_stage2 import post,created,resource
from app.platform.db.commands import now
from app.platform.db.models import PrivateFile,CredentialRef,ImportBatch,ReminderItem,ResourcePerson
from app.platform.http.errors import ApiException
from app.modules.integrations.application.service import run_once

pytestmark=DB_TESTS


def test_financial_aggregates_and_basic_plan_follow_object_scope(identity_env):
    env=identity_env;one=resource(env,'service_subscription',name='Visible subscription');two=resource(env,'service_subscription',name='Hidden subscription')
    for row,amount in [(one,'15.00'),(two,'900.00')]:
        ledger=created(post(env.admin,'/subscriptions',{'resource_id':row['id'],'plan':'Standard','seats_total':5,'seats_assigned':2}))
        created(post(env.admin,f"/subscriptions/{ledger['id']}/expenses",{'expected_version':1,'amount':amount,'currency':'CNY','kind':'actual','recorded_on':'2026-10-18','source':'Synthetic payment'}))
    manager,_=env.member('finance-scope-manager','resource_manager',[{'kind':'resource','target_id':one['id'],'permission':'read'}])
    data=created(manager.get('/api/v1/expense-summary'))['items'];assert len(data)==1 and data[0]['amount']=='15.00'
    assert created(manager.get('/api/v1/subscriptions'))['pagination']['total']==1
    member,_=env.member('basic-member',scopes=[{'kind':'resource','target_id':one['id'],'permission':'read'}])
    view=created(member.get('/api/v1/resources/'+one['id']))
    assert view['subscription_summary']['plan']=='Standard' and view['subscription_summary']['seats_assigned']==2
    assert member.get('/api/v1/subscriptions').status_code==403
    assert '900.00' not in member.get('/api/v1/exports/resources').text


def test_private_upload_compensates_failed_transaction_and_enforces_policy(identity_env):
    env=identity_env;r=resource(env)
    def upload(filename='evidence.txt',body=b'Ordinary synthetic evidence'):
        return env.admin.post('/api/v1/files',params={'resource_id':r['id'],'filename':filename},content=body,headers={'Content-Type':'application/octet-stream','Idempotency-Key':str(uuid4())})
    with patch('app.modules.materials.application.files.record_event',side_effect=ApiException(503,'DEPENDENCY_UNAVAILABLE','Synthetic unavailable audit')):
        assert upload().status_code==503
    with Session(env.engine) as db:assert db.scalar(select(func.count()).select_from(PrivateFile))==0
    assert list(Path(env.settings.private_file_root).glob('*.bin'))==[]
    env.admin.app.state.settings=env.settings.model_copy(update={'attachment_scan_required':True})
    assert upload().status_code==503
    env.admin.app.state.settings=env.settings
    assert upload('evidence.pdf',b'not PDF').status_code==422
    assert upload('program.exe',b'MZ executable').status_code==422
    member,_=env.member('material-author')
    own=created(post(member,'/resources',{'name':'Private own material probe','type_code':'application'}))
    assert post(member,f"/resources/{own['id']}/materials",{'kind':'note','body':'Ordinary text','classification':'restricted'}).status_code==403


def test_bound_stage_is_subject_specific_single_use_under_concurrency(identity_env):
    env=identity_env;r=resource(env,'api_key')
    stage=created(post(env.admin,f"/resources/{r['id']}/secret-stages",{'kind':'api_key','secret_value':'synthetic-one-use-value'}))
    manager,_=env.member('other-secret-author','resource_manager',[{'kind':'resource','target_id':r['id'],'permission':'manage'}])
    payload={'expected_version':1,'kind':'api_key','stage_token':stage['stage_token']}
    assert post(manager,f"/resources/{r['id']}/credentials",payload).status_code==410
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda _:post(env.admin,f"/resources/{r['id']}/credentials",payload),range(2)))
    assert sorted(x.status_code for x in responses)==[202,409]
    with Session(env.engine) as db:assert db.scalar(select(func.count()).select_from(CredentialRef))==1


def test_due_reminders_reads_and_expired_previews_are_worker_owned(identity_env):
    env=identity_env
    from app.modules.subscriptions.application.service import workspace_today
    today=workspace_today();domain=resource(env,'domain',attributes={'domain_name':'example.test','expires_on':(today+timedelta(days=5)).isoformat()})
    preview=created(post(env.admin,'/imports/preview',{'type_code':'application','label':'Expiring preview','csv_content':'name\nNever committed\n'}))
    with Session(env.engine) as db:db.get(ImportBatch,UUID(preview['id'])).expires_at=now()-timedelta(seconds=1);db.commit()
    run_once(env.engine,env.settings,worker_id='maintenance-proof')
    member,_=env.member('reminder-reader',scopes=[{'kind':'resource','target_id':domain['id'],'permission':'read'}])
    reminders=created(member.get('/api/v1/reminders'))['items']
    assert len(reminders)==1 and reminders[0]['window_days']==7 and not reminders[0]['read']
    created(post(member,f"/reminders/{reminders[0]['id']}/actions/read"))
    assert created(member.get('/api/v1/reminders'))['items'][0]['read']
    assert not created(env.admin.get('/api/v1/reminders'))['items'][0]['read']
    with Session(env.engine) as db:
        row=db.get(ImportBatch,UUID(preview['id']));assert row.status=='expired' and not row.rows
    assert post(env.admin,f"/imports/{preview['id']}/actions/commit",{'expected_version':1}).status_code==410
