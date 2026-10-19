from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_local_identity import identity_env,DB_TESTS
from test_stage2 import post,created,resource
from app.platform.db.models import ChangeItem

pytestmark=DB_TESTS


def test_failed_execution_rework_and_partial_case_close_preserve_history(identity_env):
    env=identity_env;reviewer,account=env.member('closure-reviewer','admin')
    actor=created(env.admin.get('/api/v1/auth/session'))['person_id']
    first=resource(env,name='Change with evidence');second=resource(env,name='Cancelled change')
    case=created(post(env.admin,'/change-cases',{'case_type':'change','coordinator_person_id':actor,'reason':'Synthetic mixed case'}))
    items=[created(post(env.admin,f"/change-cases/{case['id']}/items",{'resource_id':r['id'],'proposal':{'action':'grant_use','person_id':account['person_id']}})) for r in (first,second)]
    current=created(env.admin.get('/api/v1/change-cases/'+case['id']))
    created(post(env.admin,f"/change-cases/{case['id']}/actions/submit",{'expected_version':current['version']}))
    item=items[0];evidence=created(post(env.admin,f"/resources/{first['id']}/materials",{'kind':'note','body':'Synthetic provider evidence for an access change'}))
    item=created(post(env.admin,f"/change-items/{item['id']}/actions/start",{'expected_version':item['version']}))
    item=created(post(env.admin,f"/change-items/{item['id']}/actions/record-execution",{'expected_version':item['version'],'evidence_ids':[evidence['id']],'non_secret_result':'Synthetic provider denied the first operation','outcome':'failed'}))
    assert item['status']=='failed'
    assert post(reviewer,f"/change-items/{item['id']}/actions/confirm",{'expected_version':item['version'],'confirmation_note':'Must refuse failed work'}).status_code==409
    for attempt in range(2):
        item=created(post(env.admin,f"/change-items/{item['id']}/actions/start",{'expected_version':item['version']}))
        item=created(post(env.admin,f"/change-items/{item['id']}/actions/record-execution",{'expected_version':item['version'],'evidence_ids':[evidence['id']],'non_secret_result':'Synthetic provider operation completed; evidence checked'}))
        if attempt==0:
            created(env.admin.patch(f"/api/v1/resources/{first['id']}/materials/{evidence['id']}",json={'expected_version':1,'kind':'note','changes':{'body':'Synthetic evidence revised after execution'}}))
            response=post(reviewer,f"/change-items/{item['id']}/actions/confirm",{'expected_version':item['version'],'confirmation_note':'Must recheck revised evidence'})
            assert response.status_code==409 and response.json()['error']['code']=='EVIDENCE_CHANGED'
            item=created(post(reviewer,f"/change-items/{item['id']}/actions/return-for-rework",{'expected_version':item['version'],'reason':'Need an additional check'}))
            assert item['status']=='failed'
    created(post(reviewer,f"/change-items/{item['id']}/actions/confirm",{'expected_version':item['version'],'confirmation_note':'Independently verified'}))
    created(post(env.admin,f"/change-items/{items[1]['id']}/actions/request-cancellation",{'expected_version':items[1]['version'],'reason':'No longer required; not executed'}))
    current=created(env.admin.get('/api/v1/change-cases/'+case['id']))
    assert post(env.admin,f"/change-cases/{case['id']}/actions/close",{'expected_version':current['version']}).status_code==422
    closed=created(post(env.admin,f"/change-cases/{case['id']}/actions/close",{'expected_version':current['version'],'closure_note':'One actual change succeeded; the unexecuted second change was explicitly cancelled'}))
    assert closed['status']=='completed_with_exceptions'
    saved=created(env.admin.get('/api/v1/change-items/'+item['id']))
    assert len(saved['execution_history'])==4
    assert saved['executed_by_person_id']!=saved['confirmed_by_person_id']


def test_directory_crud_does_not_bypass_auth_or_public_company_write_scope(identity_env):
    env=identity_env
    person=created(post(env.admin,'/people',{'display_name':'Synthetic non-login person'}))
    assert created(env.admin.get('/api/v1/people/'+person['id']))['display_name']=='Synthetic non-login person'
    updated=created(env.admin.patch('/api/v1/people/'+person['id'],json={'expected_version':1,'display_name':'Updated directory name'},headers={'Idempotency-Key':'a409cc1d-d15d-45e7-9d94-8305c07e1320'}))
    assert updated['version']==2
    actor=created(env.admin.get('/api/v1/auth/session'))['person_id']
    assert env.admin.patch('/api/v1/people/'+actor,json={'expected_version':1,'display_name':'Cannot bypass auth administration'},headers={'Idempotency-Key':'9cdd3bfa-e89e-4ca0-9567-4989a8765009'}).status_code==409
    company=created(post(env.admin,'/companies',{'name':'Synthetic shared company'}))
    r=resource(env,company_links=[{'company_id':company['id'],'role':'represented'}])
    manager,_=env.member('catalog-read-manager','resource_manager',[{'kind':'resource','target_id':r['id'],'permission':'read'}])
    assert manager.get('/api/v1/directory/company/'+company['id']).status_code==200
    assert manager.patch('/api/v1/directory/company/'+company['id'],json={'expected_version':1,'name':'Unauthorized edit'},headers={'Idempotency-Key':'5cbac329-223f-423e-b71d-ef96c13b7cb9'}).status_code==403
    identity=created(post(env.admin,'/contact-identities',{'kind':'third_party','value':'synthetic-id','provider':'Synthetic provider'}))
    assert env.admin.patch('/api/v1/contact-identities/'+identity['id'],json={'expected_version':1,'value':'forbidden raw rewrite'},headers={'Idempotency-Key':'61aa00e4-7a9b-45f3-ab97-a2b7cc9d08fd'}).status_code==422
