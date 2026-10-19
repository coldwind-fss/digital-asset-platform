from datetime import timedelta
from decimal import Decimal
from uuid import UUID,uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
import base64
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from test_local_identity import identity_env,DB_TESTS
from test_stage2 import post,created,resource
from test_stage2_flows import prepare_flow,attach
from app.platform.db.models import Resource,ResourcePerson,ResourceCompany,AccountBinding,Account,ResourceRelation,CredentialRef,CredentialGrant,SyncJob,MetricSnapshot,PrivateFile,PlatformConnection,ImportBatch,ChangeItem,AuditEvent
from app.platform.db.commands import now
from app.modules.integrations.application.service import run_once
from app.modules.integrations.application.deepseek import parse_balances,AdapterError
from app.modules.credentials.application.crypto import decrypt_secret
from app.modules.credentials.application.key_rotation import rotate_material

pytestmark=DB_TESTS


def confirm(env,reviewer,r,proposal):
    item,case=prepare_flow(env,r,proposal)
    result=created(post(reviewer,f"/change-items/{item['id']}/actions/confirm",{'expected_version':item['version'],'confirmation_note':'Independent synthetic evidence review'}))
    assert result['status']=='completed'
    return result


def test_all_non_secret_governance_actions_write_their_own_facts(identity_env):
    env=identity_env;reviewer,account=env.member('all-actions-reviewer','admin')
    person=account['person_id'];actor=created(env.admin.get('/api/v1/auth/session'))['person_id']
    company=created(post(env.admin,'/companies',{'name':'Synthetic organization'}))
    for action in ['change_owner','grant_use','remove_use','transfer_controller','change_organization','change_visibility','disable_resource','retire_resource','reactivate_resource']:
        r=resource(env,name='Synthetic '+action);proposal={'action':action}
        if action in {'change_owner','remove_use','transfer_controller'}:
            role={'change_owner':'owner','remove_use':'use','transfer_controller':'controller'}[action]
            r=created(post(env.admin,f"/resources/{r['id']}/actions/initial-facts",{'expected_version':1,'people':[{'person_id':actor,'role':role}],'source_note':'Synthetic existing fact'}))
            with Session(env.engine) as db:assignment=db.scalar(select(ResourcePerson).where(ResourcePerson.resource_id==UUID(r['id']))).id
            proposal['assignment_id']=str(assignment)
            if action!='remove_use':proposal['to_person_id']=person
        if action=='grant_use':proposal['person_id']=person
        if action=='change_organization':proposal['company_id']=company['id']
        if action=='change_visibility':proposal['visibility_scope']='company'
        if action in {'retire_resource','reactivate_resource'}:
            with Session(env.engine) as db:db.get(Resource,UUID(r['id'])).lifecycle='disabled';db.commit()
        confirm(env,reviewer,r,proposal)
        with Session(env.engine) as db:
            saved=db.get(Resource,UUID(r['id']))
            if action in {'disable_resource','retire_resource','reactivate_resource'}:assert saved.lifecycle=={'disable_resource':'disabled','retire_resource':'retired','reactivate_resource':'in_use'}[action]
            if action=='change_visibility':assert saved.visibility_scope=='company'
            if action=='change_organization':assert db.scalar(select(ResourceCompany.company_id).where(ResourceCompany.resource_id==saved.id,ResourceCompany.valid_to.is_(None)))==UUID(company['id'])
            if action=='remove_use':assert db.get(ResourcePerson,assignment).valid_to
            if action in {'change_owner','grant_use','transfer_controller'}:assert db.scalar(select(ResourcePerson.person_id).where(ResourcePerson.resource_id==saved.id,ResourcePerson.valid_to.is_(None)))==UUID(person)
    old=resource(env,'api_key',name='Synthetic old Key');replacement=resource(env,'api_key',name='Synthetic replacement Key')
    confirm(env,reviewer,old,{'action':'replace_key','replacement_resource_id':replacement['id']})
    assert created(env.admin.get('/api/v1/resources/'+old['id']))['lifecycle']=='disabled'
    source=resource(env,'api_service');a=resource(env,'platform_account',name='Controller A');b=resource(env,'platform_account',name='Controller B')
    relation=created(post(env.admin,f"/resources/{source['id']}/relations",{'expected_version':1,'target_id':a['id'],'relation_type':'managed_by'}))
    source=created(env.admin.get('/api/v1/resources/'+source['id']))
    confirm(env,reviewer,source,{'action':'change_management_relation','relation_id':relation['id'],'proposed_target_id':b['id']})
    relations=created(env.admin.get(f"/api/v1/resources/{source['id']}/relations"))['items']
    assert len(relations)==1 and relations[0]['target']['id']==b['id'] and relations[0]['confirmation']=='confirmed'


def test_binding_and_mailbox_changes_work_for_scoped_independent_reviewer(identity_env):
    env=identity_env
    for kind,action in [('platform_account','change_binding'),('mailbox_account','change_mailbox_address')]:
        r=resource(env,kind)
        initial=created(post(env.admin,'/contact-identities',{'kind':'email','value':'initial@example.test'}))
        target=created(post(env.admin,'/contact-identities',{'kind':'email','value':'changed@example.test'}))
        binding=created(post(env.admin,f"/resources/{r['id']}/bindings",{'expected_version':1,'purpose':'login','contact_identity_id':initial['id']}))
        reviewer,_=env.member('binding-reviewer-'+kind,'resource_manager',[{'kind':'resource','target_id':r['id'],'permission':'manage'}])
        r=created(env.admin.get('/api/v1/resources/'+r['id']))
        confirm(env,reviewer,r,{'action':action,'binding_id':binding['id'],'new_contact_identity_id':target['id']})
        rows=created(env.admin.get(f"/api/v1/resources/{r['id']}/bindings"))['items']
        assert len(rows)==1 and rows[0]['contact']['id']==target['id']
        if kind=='mailbox_account':
            with Session(env.engine) as db:
                account=db.get(Account,UUID(r['id']))
                assert decrypt_secret(env.settings,ciphertext=account.identifier_ciphertext,nonce=account.identifier_nonce,key_version=account.key_version,associated_data=f"account-identifier:{r['id']}".encode())=='changed@example.test'


def test_revoke_credential_and_grant_take_effect_only_on_confirmation(identity_env):
    env=identity_env;reviewer,_=env.member('revoke-reviewer','admin')
    actor=created(env.admin.get('/api/v1/auth/session'))['person_id']
    for action in ['revoke_credential_grant','revoke_credential']:
        r=resource(env,'api_key');credential=attach(env,r)
        grant=None;version=1
        if action=='revoke_credential_grant':
            grant=created(post(env.admin,f'/credentials/{credential}/grants',{'person_id':actor,'capability':'view','valid_to':(now()+timedelta(hours=1)).isoformat(),'reason':'Synthetic limited grant','expected_version':1}));version=2
            assert post(env.admin,f'/credentials/{credential}/grants',{'person_id':actor,'capability':'view','valid_to':(now()+timedelta(hours=1)).isoformat(),'reason':'Duplicate','expected_version':2}).status_code==409
        operation=created(post(env.admin,f'/credentials/{credential}/operations',{'expected_version':version,'action':'revoke_grant' if grant else 'revoke','grant_id':grant['id'] if grant else None,'reason':'Synthetic revocation'}))
        r=created(env.admin.get('/api/v1/resources/'+r['id']))
        proposal={'action':action,'operation_id':operation['id'],**({'credential_grant_id':grant['id']} if grant else {'credential_id':credential})}
        confirm(env,reviewer,r,proposal)
        assert post(env.admin,f'/credentials/{credential}/actions/reveal',{'reason':'Must now be denied'}).status_code in {403,404}
        with Session(env.engine) as db:
            if grant:assert db.get(CredentialGrant,UUID(grant['id'])).valid_to<=now()
            else:assert db.get(CredentialRef,UUID(credential)).status=='revoked'


def test_concurrent_confirmation_once_and_changed_facts_rejected(identity_env):
    env=identity_env;reviewer,account=env.member('concurrent-reviewer','admin')
    r=resource(env);item,case=prepare_flow(env,r,{'action':'grant_use','person_id':account['person_id']})
    path=f"/change-items/{item['id']}/actions/confirm";payload={'expected_version':item['version'],'confirmation_note':'Concurrent replay'};key=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda _:post(reviewer,path,payload,key),range(2)))
    assert [r.status_code for r in responses]==[200,200],[r.text for r in responses]
    with Session(env.engine) as db:assert db.scalar(select(func.count()).select_from(ResourcePerson).where(ResourcePerson.resource_id==UUID(r['id']),ResourcePerson.role=='use'))==1
    another=resource(env);item,case=prepare_flow(env,another,{'action':'disable_resource'})
    actor=created(env.admin.get('/api/v1/auth/session'))['person_id']
    current=created(env.admin.get('/api/v1/resources/'+another['id']))
    created(post(env.admin,f"/resources/{another['id']}/actions/initial-facts",{'expected_version':current['version'],'people':[{'person_id':actor,'role':'owner'}],'source_note':'New authoritative fact'}))
    assert post(reviewer,f"/change-items/{item['id']}/actions/confirm",{'expected_version':item['version'],'confirmation_note':'Stale'}).status_code==409


def test_import_rechecks_references_and_rolls_back_all_rows(identity_env):
    env=identity_env;platform=created(post(env.admin,'/platforms',{'name':'Synthetic imported platform'}))
    second_platform=created(post(env.admin,'/platforms',{'name':'Synthetic removed platform'}))
    batch=created(post(env.admin,'/imports/preview',{'type_code':'cloud_resource','label':'Atomic probe','csv_content':f"name,platform_id,external_instance_id\nFirst,{platform['id']},instance-1\nSecond,{second_platform['id']},instance-2\n"}))
    with Session(env.engine) as db:
        from app.platform.db.models import Platform
        db.delete(db.get(Platform,UUID(second_platform['id'])));db.commit()
    response=post(env.admin,f"/imports/{batch['id']}/actions/commit",{'expected_version':1})
    assert response.status_code==404,(response.text,batch['results'])
    assert created(env.admin.get('/api/v1/resources'))['pagination']['total']==0
    with Session(env.engine) as db:assert db.get(ImportBatch,UUID(batch['id'])).status=='preview'


def test_master_key_rotation_is_atomic_and_old_backup_ciphertext_remains_readable(identity_env):
    env=identity_env;r=resource(env,'api_key');credential=attach(env,r)
    new_key=base64.urlsafe_b64encode(bytes(range(32))).decode()
    settings=env.settings.model_copy(update={'credential_master_key':new_key,'credential_key_version':'stage2-new-key','credential_read_keys':{env.settings.credential_key_version:env.settings.credential_master_key}})
    with Session(env.engine) as db:
        old=db.get(CredentialRef,UUID(credential));old_material=(old.ciphertext,old.nonce,old.key_version)
        counts=rotate_material(db,settings);assert counts['rows_reencrypted']>=1;db.rollback()
    with Session(env.engine) as db:
        assert db.get(CredentialRef,UUID(credential)).key_version==old_material[2]
        rotate_material(db,settings);db.commit()
    with Session(env.engine) as db:
        saved=db.get(CredentialRef,UUID(credential))
        assert decrypt_secret(settings,ciphertext=saved.ciphertext,nonce=saved.nonce,key_version=saved.key_version,associated_data=f'credential:{credential}'.encode())=='synthetic-private-value'
    assert decrypt_secret(env.settings,ciphertext=old_material[0],nonce=old_material[1],key_version=old_material[2],associated_data=f'credential:{credential}'.encode())=='synthetic-private-value'


def test_worker_concurrent_claim_and_stale_lease_never_duplicate_snapshot(identity_env):
    env=identity_env;r=resource(env,'api_key');credential=attach(env,r)
    connection=created(post(env.admin,'/platform-connections',{'resource_id':r['id'],'credential_id':credential,'provider':'deepseek','label':'Concurrent synthetic probe'}))
    job=created(post(env.admin,f"/platform-connections/{connection['id']}/actions/sync"))
    balance=parse_balances({'is_available':True,'balance_infos':[{'currency':'USD','total_balance':'1','granted_balance':'0','topped_up_balance':'1'}]})
    started,release=Event(),Event()
    def slow(secret):started.set();assert release.wait(10);return balance
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(run_once,env.engine,env.settings,fetcher=slow,worker_id='first-worker')
        assert started.wait(10)
        second=run_once(env.engine,env.settings,fetcher=lambda _:balance,worker_id='second-worker')
        assert not second['processed'];release.set();assert first.result()['status']=='succeeded'
    with Session(env.engine) as db:assert db.scalar(select(func.count()).select_from(MetricSnapshot))==1
    job=created(post(env.admin,f"/platform-connections/{connection['id']}/actions/sync"))
    def stale(secret):
        with Session(env.engine) as db:db.get(SyncJob,UUID(job['id'])).lease_token=uuid4();db.commit()
        return balance
    assert run_once(env.engine,env.settings,fetcher=stale,worker_id='stale-worker')['discarded_stale_lease']
    with Session(env.engine) as db:assert db.scalar(select(func.count()).select_from(MetricSnapshot))==1
