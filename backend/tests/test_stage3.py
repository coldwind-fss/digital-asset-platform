"""Stage 3 projections must not weaken the Stage 2 command boundaries."""
from uuid import UUID, uuid4
import pytest
from sqlalchemy.orm import Session
from test_local_identity import identity_env, DB_TESTS
from test_stage2 import post, created, resource
from app.platform.db.models import Resource, ResourceRelation
from datetime import date,timedelta

pytestmark=DB_TESTS

def test_graph_same_facts_scope_direction_and_safe_identity(identity_env):
    env=identity_env
    platform=created(post(env.admin,'/platforms',{'name':'Graph platform'}))
    hidden=resource(env,name='Hidden graph resource',platform_id=platform['id'])
    member,person=env.member('map-member')
    visible=created(post(member,'/resources',{'name':'Visible member resource','type_code':'application','platform_id':platform['id']}))
    relation=created(post(env.admin,f"/resources/{visible['id']}/relations",{'expected_version':visible['version'],'target_id':hidden['id'],'relation_type':'uses'}))
    graph=created(member.get(f"/api/v1/asset-graph?kind=resource&object_id={visible['id']}&depth=2"))
    assert graph['center']=='resource:'+visible['id']
    assert not any(n['id']==hidden['id'] for n in graph['nodes'])
    assert all(e['id']!=relation['id'] for e in graph['edges'])
    assert 'graph-synthetic@example.test' not in str(graph)
    keys={n['key'] for n in graph['nodes']}
    assert all(e['source'] in keys and e['target'] in keys for e in graph['edges'])
    assert member.get(f"/api/v1/asset-graph?kind=resource&object_id={hidden['id']}").status_code==404
    assert member.get(f"/api/v1/asset-graph?kind=resource&object_id={visible['id']}&depth=3").status_code==422
    full=created(env.admin.get(f"/api/v1/asset-graph?kind=resource&object_id={visible['id']}"))
    edge=next(e for e in full['edges'] if e['id']==relation['id'])
    assert edge['source']=='resource:'+visible['id'] and edge['target']=='resource:'+hidden['id']

def test_graph_bound_is_visible_and_declares_truncation(identity_env):
    env=identity_env
    center=resource(env,name='Graph cap center')
    with Session(env.engine) as db:
        actor=UUID(created(env.admin.get('/api/v1/auth/session'))['person_id'])
        for i in range(105):
            target=Resource(id=uuid4(),code=f'GRAPH-{i:04}',name=f'Graph sample {i}',type_code='application',created_by_person_id=actor)
            db.add(target);db.flush()
            db.add(ResourceRelation(source_resource_id=UUID(center['id']),target_resource_id=target.id,relation_type='uses',confirmation='proposed'))
        db.commit()
    graph=created(env.admin.get(f"/api/v1/asset-graph?kind=resource&object_id={center['id']}"))
    assert graph['truncated'] is True and len(graph['nodes'])<=100 and len(graph['edges'])<=200
    assert len(graph['nodes'])==100

def test_graph_identity_reverse_declarations_and_roles_never_expose_protected_values(identity_env):
    env=identity_env
    account=resource(env,'platform_account',account={'identifier':'protected-account@example.test'})
    identity=created(post(env.admin,'/contact-identities',{'kind':'email','value':'protected-contact@example.test','label':'Synthetic safe label'}))
    created(post(env.admin,f"/resources/{account['id']}/bindings",{'expected_version':account['version'],'purpose':'recovery','contact_identity_id':identity['id']}))
    account=created(env.admin.get('/api/v1/resources/'+account['id']))
    created(post(env.admin,f"/resources/{account['id']}/relation-declarations",{'expected_version':account['version'],'relation_kind':'managed_by','state':'not_applicable','reason':'Synthetic standalone account','source':'Synthetic test'}))
    graph=created(env.admin.get(f"/api/v1/asset-graph?kind=identity&object_id={identity['id']}"))
    assert any(n['id']==account['id'] for n in graph['nodes'])
    assert 'protected-contact@example.test' not in str(graph) and 'protected-account@example.test' not in str(graph)
    node=next(n for n in graph['nodes'] if n['id']==account['id'])
    assert node['declarations']==[{'relation_kind':'managed_by','state':'not_applicable'}]
    assert not any(e['relation']=='managed_by' for e in graph['edges'])
    member,person=env.member('roles-reader','member',[{'kind':'resource','target_id':account['id'],'permission':'read'}])
    me=created(env.admin.get('/api/v1/auth/session'))['person_id']
    account=created(env.admin.get('/api/v1/resources/'+account['id']))
    created(post(env.admin,f"/resources/{account['id']}/actions/initial-facts",{'expected_version':account['version'],'people':[{'person_id':me,'role':'owner'}],'source_note':'Synthetic visible role'}))
    hidden=resource(env)
    created(post(env.admin,f"/resources/{hidden['id']}/actions/initial-facts",{'expected_version':hidden['version'],'people':[{'person_id':me,'role':'owner'}],'source_note':'Synthetic hidden role'}))
    roles=created(member.get('/api/v1/resource-roles'))
    assert roles['pagination']['total']==1 and roles['items'][0]['resource_id']==account['id']
    assert member.get('/api/v1/admin/departments').status_code==403
    assert created(env.admin.get('/api/v1/admin/departments'))['pagination']['total']==0

def test_personal_preferences_are_versioned_and_never_complete_business_reminders(identity_env):
    env=identity_env;member,_=env.member('preferences-member')
    assert created(env.admin.get('/api/v1/me/notification-preferences'))=={'show_due':True,'version':1}
    response=env.admin.patch('/api/v1/me/notification-preferences',json={'expected_version':1,'show_due':False},headers={'Idempotency-Key':str(uuid4())})
    assert created(response)=={'show_due':False,'version':2}
    assert created(member.get('/api/v1/me/notification-preferences'))=={'show_due':True,'version':1}
    assert env.admin.patch('/api/v1/me/notification-preferences',json={'expected_version':1,'show_due':True},headers={'Idempotency-Key':str(uuid4())}).status_code==409
    assert created(env.admin.get('/api/v1/reminders'))['pagination']['total']==0

def test_allowed_actions_follow_assignee_independent_review_and_role_scope(identity_env):
    env=identity_env;r=resource(env)
    manager,person=env.member('ui-manager','resource_manager',[{'kind':'resource','target_id':r['id'],'permission':'manage'}])
    me=created(env.admin.get('/api/v1/auth/session'))['person_id']
    case=created(post(env.admin,'/change-cases',{'case_type':'change','coordinator_person_id':me,'reason':'Synthetic independent UI review'}))
    assert case['available_actions']==['edit','add-item']
    item=created(post(env.admin,f"/change-cases/{case['id']}/items",{'resource_id':r['id'],'assignee_person_id':person['person_id'],'proposal':{'action':'grant_use','person_id':person['person_id']}}))
    case=created(env.admin.get('/api/v1/change-cases/'+case['id']))
    assert 'submit' in case['available_actions']
    created(post(env.admin,f"/change-cases/{case['id']}/actions/submit",{'expected_version':case['version']}))
    admin_item=created(env.admin.get('/api/v1/change-items/'+item['id']))
    assert 'start' not in admin_item['available_actions']
    item=created(manager.get('/api/v1/change-items/'+item['id']))
    assert 'start' in item['available_actions']
    item=created(post(manager,f"/change-items/{item['id']}/actions/start",{'expected_version':item['version']}))
    evidence=created(post(env.admin,f"/resources/{r['id']}/materials",{'kind':'note','title':'Actual synthetic evidence','body':'Manual synthetic access checked.'}))
    item=created(post(manager,f"/change-items/{item['id']}/actions/record-execution",{'expected_version':item['version'],'outcome':'succeeded','non_secret_result':'Synthetic access was checked.','evidence_ids':[evidence['id']]}))
    assert 'confirm' not in item['available_actions']
    review=created(env.admin.get('/api/v1/change-items/'+item['id']))
    assert 'confirm' in review['available_actions'] and 'record-execution' not in review['available_actions']
    assert created(env.admin.get('/api/v1/resource-roles'))['pagination']['total']==0
    created(post(env.admin,f"/change-items/{item['id']}/actions/confirm",{'expected_version':item['version'],'confirmation_note':'Independent synthetic reviewer checked evidence.'}))
    roles=created(env.admin.get('/api/v1/resource-roles?resource_id='+r['id']))
    assert roles['items'][0]['person_id']==person['person_id'] and roles['items'][0]['role']=='use'

def test_search_applies_to_my_resources_and_safe_identity_metadata(identity_env):
    env=identity_env
    me=created(env.admin.get('/api/v1/auth/session'))['person_id']
    first=resource(env,name='Searchable resource',purpose='UniquePurposeNeedle')
    second=resource(env,name='Another resource',purpose='Other purpose')
    for row in (first,second):
        created(post(env.admin,f"/resources/{row['id']}/actions/initial-facts",{'expected_version':row['version'],'people':[{'person_id':me,'role':'owner'}],'source_note':'Synthetic search fixture'}))
    for path in ('/resources','/me/resources'):
        found=created(env.admin.get('/api/v1'+path,params={'q':'UniquePurposeNeedle'}))
        assert found['pagination']['total']==1 and found['items'][0]['id']==first['id']
        assert created(env.admin.get('/api/v1'+path,params={'q':'NoMatchingName'}))['pagination']['total']==0
    identity=created(post(env.admin,'/contact-identities',{'kind':'email','value':'secret-search-identity@example.test','label':'MetadataNeedle'}))
    assert created(env.admin.get('/api/v1/contact-identities',params={'q':'MetadataNeedle'}))['pagination']['total']==1
    assert created(env.admin.get('/api/v1/contact-identities',params={'q':'secret-search-identity@example.test'}))['pagination']['total']==0
    member,_=env.member('search-scope-member')
    assert created(member.get('/api/v1/contact-identities',params={'q':'MetadataNeedle'}))['pagination']['total']==0

def test_reminder_unread_counts_and_connection_job_filters_match_scope(identity_env):
    env=identity_env
    r=resource(env,'service_subscription')
    ledger=created(post(env.admin,'/subscriptions',{'resource_id':r['id'],'plan':'Synthetic reminder plan'}))
    today=date.today()
    created(post(env.admin,f"/subscriptions/{ledger['id']}/periods",{'expected_version':ledger['version'],'starts_on':str(today-timedelta(days=30)),'ends_on':str(today+timedelta(days=1)),'currency':'CNY','source':'Synthetic reminder source'}))
    created(post(env.admin,'/reminders/actions/refresh'))
    reminders=created(env.admin.get('/api/v1/reminders'))
    assert reminders['unread_total']>0 and all(row['resource_name']==r['name'] for row in reminders['items'])
    member,_=env.member('reminder-scope-member')
    assert created(member.get('/api/v1/reminders'))['unread_total']==0
    created(post(env.admin,f"/reminders/{reminders['items'][0]['id']}/actions/read"))
    assert created(env.admin.get('/api/v1/reminders'))['unread_total']==reminders['unread_total']-1
    from test_stage2_flows import attach
    source=resource(env,'api_key');credential=attach(env,source)
    connections=[created(post(env.admin,'/platform-connections',{'resource_id':source['id'],'credential_id':credential,'label':f'Synthetic connection {i}'})) for i in range(2)]
    for connection in connections:created(post(env.admin,f"/platform-connections/{connection['id']}/actions/sync"))
    jobs=created(env.admin.get('/api/v1/sync-jobs',params={'connection_id':connections[0]['id']}))
    assert jobs['pagination']['total']==1 and jobs['items'][0]['connection_id']==connections[0]['id']
