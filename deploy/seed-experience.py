"""Explicit synthetic data/configuration; never run on startup or reset a DB.

--enable-full-product upgrades the original synthetic instance in place using
existing roles and credential services. Original read-only setup stays compatible.
"""
import argparse,json,sys
from pathlib import Path
from datetime import UTC,date,datetime,timedelta
from uuid import uuid4
from sqlalchemy import select,func,delete
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import Settings
from app.platform.db.target import create_database_engine,verify_database_identity
from app.platform.db.models import Person,Department,Company,Platform,AuthAccount,AuthScope,Resource,Account,ResourcePerson,ResourceCompany,ResourceRelation,Material,SubscriptionLedger,SubscriptionPeriod,ExpenseEntry,ChangeCase,ChangeItem,AuditEvent,CredentialRef,CredentialGrant
from app.modules.identity_access.application.passwords import password_hash,password_matches
from app.modules.identity_access.application.service import revoke_sessions,audit

SAMPLE_PASSWORD='Demo-Product-2026!'
REVIEWER_PASSWORD='Review-Product-2026!'

def enable_full_product(db,settings):
    assert not settings.read_only,'Full product requires APP_READ_ONLY=false'
    assert db.scalar(select(AuditEvent.id).where(AuditEvent.event_type=='experience.seed').limit(1)), 'Only the explicitly seeded synthetic instance may be upgraded'
    public=db.scalars(select(AuthAccount).where(AuthAccount.username.in_(['visitor','demo']))).all()
    assert len(public)==1,'Public sample identity is missing or ambiguous'
    sample=public[0]
    if sample.username=='demo':
        assert password_matches(SAMPLE_PASSWORD,sample.password_hash),'Existing sample password was changed; use the standard recovery flow instead of silently resetting it'
    sample.username='demo';sample.password_hash=password_hash(SAMPLE_PASSWORD);sample.role='admin';sample.status='active';sample.must_change_password=False;sample.version+=1
    person=db.get(Person,sample.person_id);assert person and person.status=='active'
    person.display_name='示例管理员'
    db.execute(delete(AuthScope).where(AuthScope.account_id==sample.id))
    reviewer=db.scalar(select(AuthAccount).where(AuthAccount.username=='reviewer'))
    if reviewer is None:
        reviewer_person=Person(id=uuid4(),display_name='陈悦 · 示例复核人',status='active',department_id=person.department_id)
        db.add(reviewer_person);db.flush()
        reviewer=AuthAccount(id=uuid4(),person_id=reviewer_person.id,username='reviewer',password_hash=password_hash(REVIEWER_PASSWORD),role='admin',status='active',must_change_password=False)
        db.add(reviewer);db.flush()
    else:
        assert reviewer.role=='admin' and reviewer.status=='active' and password_matches(REVIEWER_PASSWORD,reviewer.password_hash),'Existing reviewer was changed; retain it and use standard account management'
    revoke_sessions(db,sample.id);revoke_sessions(db,reviewer.id)
    for note in db.scalars(select(Material).where(Material.title=='公开体验说明')):
        if note.body=='本环境仅浏览虚构数据。正式环境支持登记、受控凭据、治理、费用、CSV和私有附件。':
            note.title='系统示例数据说明';note.body='本系统使用虚构示例数据，登记、编辑、订阅费用、受控凭据、导入附件和治理均为真实功能。执行与复核仍遵循独立确认规则。'
    audit(db,'showcase.full_product_configured',None,uuid4(),{'sample_account_id':str(sample.id),'reviewer_account_id':str(reviewer.id),'existing_role':'admin','read_only':False})
    sample_person,reviewer_person=sample.person_id,reviewer.person_id
    db.commit()
    # Seed only an unmistakably synthetic secret through its owning service.
    from app.modules.credentials.application.service import create_secret_stage,attach_credential,create_credential_grant
    from app.modules.credentials.api.schemas import SecretStageCreate,CredentialAttachRequest,CredentialGrantCreate
    resource=db.scalar(select(Resource).where(Resource.code=='DEMO-003',Resource.type_code=='api_key'))
    assert resource and resource.provider_name=='虚构展示数据'
    credential=db.scalar(select(CredentialRef).where(CredentialRef.resource_id==resource.id,CredentialRef.kind=='api_key',CredentialRef.status=='saved'))
    if credential is None:
        _,token=create_secret_stage(db,settings,SecretStageCreate(kind='api_key',secret_value='EXAMPLE-ONLY-NOT-A-REAL-API-KEY',resource_id=resource.id,purpose='attach'))
        db.refresh(resource)
        identity=attach_credential(db,settings,resource.id,CredentialAttachRequest(kind='api_key',stage_token=token,expected_version=resource.version),actor_id=sample_person,request_id=uuid4())
        credential=db.get(CredentialRef,identity)
    for person_id in [sample_person,reviewer_person]:
        for capability in ['view','rotate']:
            if not db.scalar(select(CredentialGrant.id).where(CredentialGrant.credential_id==credential.id,CredentialGrant.person_id==person_id,CredentialGrant.capability==capability,((CredentialGrant.valid_to.is_(None))|(CredentialGrant.valid_to>datetime.now(UTC))))):
                db.refresh(credential)
                create_credential_grant(db,credential.id,CredentialGrantCreate(person_id=person_id,capability=capability,valid_to=datetime.now(UTC)+timedelta(days=365),reason='虚构产品样例的显式授权',expected_version=credential.version),actor_id=sample_person,request_id=uuid4())
    print('Full product sample accounts configured with existing admin roles; synthetic credential encrypted and explicitly granted; existing business records retained.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--enable-full-product',action='store_true');args=parser.parse_args()
    config=json.loads(Path('/etc/digital-asset-platform/demo/app.json').read_text())
    settings=Settings.from_environment({k:str(v).lower() if isinstance(v,bool) else str(v) for k,v in config.items()})
    assert settings.expected_database=='digital_asset_platform_demo' and settings.instance_id=='digital-asset-platform-server-demo'
    assert (not settings.read_only) if args.enable_full_product else settings.read_only
    engine=create_database_engine(settings)
    with engine.connect() as conn:verify_database_identity(conn,expected_database=settings.expected_database,expected_instance_id=settings.instance_id,expected_environment='production')
    with Session(engine) as db:
        if db.scalar(select(func.count()).select_from(AuthAccount)):
            if args.enable_full_product:enable_full_product(db,settings)
            else:print('Existing demo data retained; no reset performed')
            return
        department=Department(id=uuid4(),name='产品研发部',status='active');db.add(department);db.flush()
        visitor=Person(id=uuid4(),display_name='只读体验访客',status='active',department_id=department.id)
        owner=Person(id=uuid4(),display_name='林晓 · 示例负责人',status='active',department_id=department.id)
        company=Company(id=uuid4(),name='星河科技（虚构）',status='active')
        platform=Platform(id=uuid4(),name='星河协作平台（虚构）',status='active',website='https://example.com')
        db.add_all([visitor,owner,company,platform]);db.flush()
        account=AuthAccount(id=uuid4(),person_id=visitor.id,username='visitor',password_hash=password_hash('Demo-ReadOnly-2026!'),role='resource_manager',status='active');db.add(account);db.flush()
        rows=[]
        data=[('platform_account','团队主账号',{}),('mailbox_account','共享通知邮箱',{}),('api_key','开发环境访问密钥',{'external_key_id':'public-example-key-id'}),('service_subscription','协作文档年度订阅',{'plan':'团队版','seats':20,'billing_cycle':'year'}),('business_space','产品研发空间',{'external_instance_id':'example-workspace','environment':'演示'}),('application','数字资产管理中台',{'endpoint':'https://example.com','tech_stack':['Vue 3','FastAPI'],'environment':'演示'}),('api_service','知识检索服务',{'endpoint':'https://example.com/api','environment':'演示'}),('cloud_resource','华东业务数据库与备份实例',{'resource_kind':'PostgreSQL','region':'华东','environment':'演示'}),('domain','公司服务域名',{'domain_name':'example.com','registrar':'虚构注册商','expires_on':str(date.today()+timedelta(days=20))})]
        for index,(kind,name,attributes) in enumerate(data):
            row=Resource(id=uuid4(),code='DEMO-'+str(index+1).zfill(3),name=name,type_code=kind,provider_name='虚构展示数据',purpose='公开体验样例，非真实企业资产',created_by_person_id=owner.id,owning_department_id=department.id,platform_id=platform.id,lifecycle='in_use',verification='verified',attributes=attributes)
            db.add(row);db.flush();rows.append(row)
            if kind in {'platform_account','mailbox_account'}:db.add(Account(resource_id=row.id,identifier_masked='d***@example.com',login_methods=['password'],account_role='master'))
            db.add_all([AuthScope(account_id=account.id,kind='resource',target_id=row.id,permission='read'),ResourcePerson(resource_id=row.id,person_id=owner.id,role='owner',confirmation='confirmed'),ResourceCompany(resource_id=row.id,company_id=company.id,role='owner',confirmation='confirmed')])
        db.add(ResourcePerson(resource_id=rows[0].id,person_id=visitor.id,role='use',confirmation='confirmed'))
        for source,target,kind in [(5,7,'depends_on'),(5,6,'uses'),(2,0,'managed_by'),(4,0,'managed_by')]:db.add(ResourceRelation(source_resource_id=rows[source].id,target_resource_id=rows[target].id,relation_type=kind,confirmation='confirmed'))
        db.add_all([Material(resource_id=rows[5].id,kind='note',title='公开体验说明',body='本环境仅浏览虚构数据。正式环境支持登记、受控凭据、治理、费用、CSV和私有附件。'),Material(resource_id=rows[5].id,kind='entry',title='示例访问入口',url='https://example.com')])
        ledger=SubscriptionLedger(id=uuid4(),resource_id=rows[3].id,plan='团队年度套餐',seats_total=20,seats_assigned=8,billing_cycle='year');db.add(ledger);db.flush()
        for index in range(3):
            starts=date.today()-timedelta(days=700-index*365);ends=starts+timedelta(days=364)
            db.add(SubscriptionPeriod(resource_id=rows[3].id,ledger_id=ledger.id,starts_on=starts,ends_on=ends,planned_amount='1200.00',currency='CNY',source='虚构年度合同',created_by_person_id=owner.id))
        for currency,amount in [('CNY','1200'),('USD','30')]:db.add(ExpenseEntry(resource_id=rows[3].id,ledger_id=ledger.id,amount=amount,currency=currency,kind='actual',recorded_on=date.today(),source='虚构费用凭证',created_by_person_id=owner.id))
        case=ChangeCase(id=uuid4(),case_type='change',reason='示例：交接平台账号负责人',coordinator_person_id=owner.id,status='draft');db.add(case);db.flush()
        db.add(ChangeItem(case_id=case.id,resource_id=rows[0].id,action='change_owner',status='pending',proposal_json={'action':'change_owner','to_person_id':str(visitor.id)},expected_resource_version=1,to_person_id=visitor.id))
        db.add(AuditEvent(actor_person_id=None,actor_kind='system',event_type='experience.seed',request_id=uuid4(),safe_after={'synthetic':True,'resources':len(rows)}))
        db.commit()
        if args.enable_full_product:enable_full_product(db,settings)
    print('Created nine synthetic resource types, directory, roles, expenses, periods and draft governance. No credentials or live connections.')

if __name__=='__main__':main()
