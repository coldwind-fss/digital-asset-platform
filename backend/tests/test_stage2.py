from datetime import date,timedelta,datetime,UTC
from uuid import UUID,uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from test_local_identity import identity_env,DB_TESTS,PASSWORD
from app.platform.db.models import Account,Resource,ContactIdentity,SubscriptionLedger,ProvenanceEntry

pytestmark=DB_TESTS


def post(client,path,payload=None,key=None):
    return client.post('/api/v1'+path,json=payload,headers={'Idempotency-Key':key or str(uuid4())})


def created(response):
    assert response.status_code in {200,201,202},response.text
    return response.json()['data']


def resource(env,type_code='application',**fields):
    return created(post(env.admin,'/resources',{'name':'Synthetic '+type_code,'type_code':type_code,**fields}))


def test_v3_core_categories_protected_identities_and_unknown_upstream(identity_env):
    env=identity_env
    company=created(post(env.admin,'/companies',{'name':'Synthetic Company'}))
    platform=created(post(env.admin,'/platforms',{'name':'Synthetic Platform','website':'https://example.test'}))
    identity=created(post(env.admin,'/contact-identities',{'kind':'third_party','value':'synthetic-registration-identity','provider':'Synthetic IdP','company_id':company['id']}))
    assert 'synthetic-registration-identity' not in str(identity)
    for kind in ['platform_account','mailbox_account','api_key','service_subscription','business_space','application','api_service','cloud_resource','domain']:
        fields={'platform_id':platform['id']}
        if kind=='mailbox_account':fields['account']={'identifier':'synthetic@example.test','aliases':['alias@example.test']}
        if kind=='domain':fields['attributes']={'domain_name':'example.test','expires_on':'2030-10-17'}
        row=resource(env,kind,**fields)
        assert row['lifecycle']=='unknown' and row['verification']=='unverified' and row['owner'] is None
        assert row['platform_id']==platform['id']
    with Session(env.engine) as db:
        assert db.scalar(select(func.count()).select_from(Account))==2
        stored=db.get(ContactIdentity,UUID(identity['id']))
        assert b'synthetic-registration-identity' not in stored.protected_value
    target=resource(env,'cloud_resource')
    declaration=created(post(env.admin,f"/resources/{target['id']}/relation-declarations",{'expected_version':target['version'],'relation_kind':'managed_by','state':'unknown','reason':'Upstream not yet known','source':'Synthetic source'}))
    assert declaration['state']=='unknown'
    manager=resource(env,'platform_account')
    current=created(env.admin.get('/api/v1/resources/'+target['id']))
    relation=created(post(env.admin,f"/resources/{target['id']}/relations",{'expected_version':current['version'],'target_id':manager['id'],'relation_type':'managed_by'}))
    incoming=created(env.admin.get(f"/api/v1/resources/{manager['id']}/relations?direction=incoming"))
    assert incoming['items'][0]['id']==relation['id']
    history=created(env.admin.get(f"/api/v1/resources/{target['id']}/relation-declarations"))
    assert history['items'][0]['ended_at']
    assert created(env.admin.get(f"/api/v1/resources/{target['id']}/sources"))['items']
    assert created(env.admin.get(f"/api/v1/resources/{target['id']}/history"))['items']


def test_transactional_retries_conflicts_and_containment_cycle(identity_env):
    env=identity_env;key=str(uuid4());payload={'name':'Retry object','type_code':'application'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies=list(pool.map(lambda _:post(env.admin,'/resources',payload,key),range(2)))
    assert all(r.status_code==201 for r in replies),[r.text for r in replies]
    assert replies[0].json()['data']['id']==replies[1].json()['data']['id']
    assert post(env.admin,'/resources',{**payload,'name':'Different'},key).status_code==409
    a=resource(env,'business_space',name='Space A');b=resource(env,'business_space',name='Space B')
    created(post(env.admin,f"/resources/{a['id']}/relations",{'expected_version':1,'target_id':b['id'],'relation_type':'contains'}))
    cycle=post(env.admin,f"/resources/{b['id']}/relations",{'expected_version':1,'target_id':a['id'],'relation_type':'contains'})
    assert cycle.status_code==409,cycle.text
    duplicate=post(env.admin,f"/resources/{b['id']}/relations",{'expected_version':1,'target_id':a['id'],'relation_type':'part_of'})
    assert duplicate.status_code==409,duplicate.text


def test_initial_facts_and_governed_patch_boundary(identity_env):
    env=identity_env;row=resource(env)
    me=created(env.admin.get('/api/v1/auth/session'))
    fixed=created(post(env.admin,f"/resources/{row['id']}/actions/initial-facts",{'expected_version':row['version'],'people':[{'person_id':me['person_id'],'role':'owner'}],'source_note':'Synthetic verified record'}))
    assert fixed['owner']['id']==me['person_id']
    assert post(env.admin,f"/resources/{row['id']}/actions/initial-facts",{'expected_version':fixed['version'],'people':[{'person_id':me['person_id'],'role':'owner'}],'source_note':'Cannot overwrite'}).status_code==409
    assert env.admin.patch('/api/v1/resources/'+row['id'],json={'expected_version':fixed['version'],'changes':{'lifecycle':'disabled'}}).status_code==422
    mine=created(env.admin.get('/api/v1/me/resources'))
    assert any(x['id']==row['id'] and 'owner' in x['my_roles'] for x in mine['items'])


def test_subscription_ledger_currency_periods_corrections_and_permissions(identity_env):
    env=identity_env;r=resource(env,'service_subscription')
    ledger=created(post(env.admin,'/subscriptions',{'resource_id':r['id'],'plan':'Synthetic Plan','seats_total':10,'seats_assigned':3}))
    current=created(post(env.admin,f"/subscriptions/{ledger['id']}/periods",{'expected_version':1,'starts_on':'2026-10-01','ends_on':'2026-10-31','currency':'CNY','planned_amount':None,'source':'Synthetic initial term'}))
    assert current['planned_amount'] is None
    assert post(env.admin,f"/subscriptions/{ledger['id']}/periods",{'expected_version':2,'starts_on':'2026-10-31','ends_on':'2026-11-30','currency':'CNY','planned_amount':'10.00','source':'Overlapping term'}).status_code==409
    for currency,amount,version in [('CNY','20.00',2),('USD','5.00',3)]:
        created(post(env.admin,f"/subscriptions/{ledger['id']}/expenses",{'expected_version':version,'amount':amount,'currency':currency,'kind':'actual','recorded_on':'2026-10-17','source':'Synthetic payment'}))
    summary=created(env.admin.get('/api/v1/expense-summary'))['items']
    assert {(x['currency'],x['amount']) for x in summary}=={('CNY','20.00'),('USD','5.00')}
    member,_=env.member(scopes=[{'kind':'resource','target_id':r['id'],'permission':'read'}])
    assert member.get('/api/v1/subscriptions/'+ledger['id']).status_code==403
    assert member.get('/api/v1/expense-summary').status_code==403
    assert post(member,'/subscriptions',{'resource_id':r['id']}).status_code==403
    next_term=created(post(env.admin,f"/subscriptions/{ledger['id']}/periods",{'expected_version':4,'starts_on':'2026-11-01','ends_on':'2026-11-30','currency':'CNY','planned_amount':'25.00','source':'Synthetic renewal'}))
    current_ledger=created(env.admin.get('/api/v1/subscriptions/'+ledger['id']))
    assert current_ledger['current_period']['id']==current['id']
    assert current_ledger['seats_assigned']==3 and current_ledger['active_users']==0
