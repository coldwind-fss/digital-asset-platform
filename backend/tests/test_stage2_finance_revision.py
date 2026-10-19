from test_local_identity import identity_env,DB_TESTS
from test_stage2 import post,created,resource

pytestmark=DB_TESTS


def test_expense_correction_keeps_original_history_and_replaces_totals(identity_env):
    env=identity_env;r=resource(env,'service_subscription')
    ledger=created(post(env.admin,'/subscriptions',{'resource_id':r['id']}))
    original=created(post(env.admin,f"/subscriptions/{ledger['id']}/expenses",{'expected_version':1,'amount':'19.00','currency':'USD','kind':'actual','recorded_on':'2026-10-18','source':'Synthetic invoice entered incorrectly'}))
    assert post(env.admin,f"/subscriptions/{ledger['id']}/expenses",{'expected_version':2,'amount':'20.00','currency':'USD','kind':'actual','recorded_on':'2026-10-18','source':'Invalid premature correction','corrects_entry_id':original['id']}).status_code==409
    voided=created(post(env.admin,f"/expenses/{original['id']}/actions/void",{'expected_version':1,'reason':'Invoice amount corrected after verification'}))
    assert voided['void_reason']
    created(post(env.admin,f"/subscriptions/{ledger['id']}/expenses",{'expected_version':3,'amount':'20.00','currency':'USD','kind':'actual','recorded_on':'2026-10-18','source':'Verified synthetic replacement invoice','corrects_entry_id':original['id']}))
    expenses=created(env.admin.get(f"/api/v1/subscriptions/{ledger['id']}/expenses"))['items']
    assert len(expenses)==2 and any(x['id']==original['id'] and x['void_reason'] for x in expenses)
    summary=created(env.admin.get('/api/v1/expense-summary'))['items']
    assert len(summary)==1 and summary[0]['amount']=='20.00' and summary[0]['currency']=='USD'


def test_type_rule_errors_are_safe_422_and_stable_external_ids_are_unique(identity_env):
    env=identity_env
    invalid=[('domain',{'domain_name':'not a domain'}),('api_service',{'endpoint':'https://user:private@example.test'}),('cloud_resource',{'secret_value':'forbidden'}),('service_subscription',{'seats':-1})]
    for type_code,attrs in invalid:
        response=post(env.admin,'/resources',{'name':'Invalid synthetic resource','type_code':type_code,'attributes':attrs})
        assert response.status_code==422,response.text
        assert response.json()['error']['code']=='VALIDATION_FAILED'
    assert created(env.admin.get('/api/v1/resources'))['pagination']['total']==0
    platform=created(post(env.admin,'/platforms',{'name':'Synthetic duplicate platform'}))
    fields={'platform_id':platform['id'],'attributes':{'external_instance_id':'same-stable-instance'}}
    resource(env,'cloud_resource',name='First visible name',**fields)
    duplicate=post(env.admin,'/resources',{'name':'Different visible name','type_code':'cloud_resource',**fields})
    assert duplicate.status_code==409
    assert created(env.admin.get('/api/v1/resources'))['pagination']['total']==1
