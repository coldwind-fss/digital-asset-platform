"""Explicit synthetic browser fixture. Runs only on the marked isolated test DB.

Never called by application startup or against workspace_dev. No real platform
requests are made: snapshot and failed job below are clearly synthetic evidence.
"""
from pathlib import Path
from datetime import UTC, datetime, timedelta, date
from uuid import UUID,uuid4
import sys,json
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_local_identity import identity_env,PASSWORD
from test_stage2 import post,created,resource
from app.platform.db.models import MetricSnapshot,SyncJob,PlatformConnection,Resource,ResourceRelation

def main():
    root=Path(__file__).resolve().parents[2]
    generator=identity_env.__wrapped__(root/'.local/workspace/stage3-browser-fixture')
    env=next(generator)
    try:
        assert env.settings.expected_database=='digital_asset_platform_workspace_test'
        admin=created(env.admin.get('/api/v1/auth/session'));admin_id=admin['person_id']
        company=created(post(env.admin,'/companies',{'name':'合成验收 · 星河科技有限公司','description':'第三阶段隔离验收数据，非真实企业资产'}))
        created(env.admin.patch('/api/v1/directory/company/'+company['id'],json={'expected_version':1,'status':'active'},headers={'Idempotency-Key':str(uuid4())}))
        platform=created(post(env.admin,'/platforms',{'name':'DeepSeek（合成验收目录）','website':'https://platform.deepseek.com'}))
        created(env.admin.patch('/api/v1/directory/platform/'+platform['id'],json={'expected_version':1,'status':'active'},headers={'Idempotency-Key':str(uuid4())}))
        resources=[]
        for kind,name,attrs in [
          ('platform_account','研发团队 · DeepSeek 主账号',{}),
          ('mailbox_account','共享邮箱 · 数字资产通知',{}),
          ('api_key','研发环境 · API 访问密钥',{'external_key_id':'synthetic-public-key-id'}),
          ('service_subscription','协作文档 · 团队订阅',{'plan':'团队年度套餐','seats':20,'billing_cycle':'year'}),
          ('business_space','产品研发 · 企业业务空间',{'external_instance_id':'synthetic-workspace','environment':'测试'}),
          ('application','数字资产管理中台 · 测试应用',{'endpoint':'https://example.test/app','environment':'测试','tech_stack':['Vue 3','FastAPI']}),
          ('api_service','客户服务 · 知识检索 API',{'endpoint':'https://example.test/api','metric_scope':'账号级余额','environment':'测试'}),
          ('cloud_resource','华东 · 业务数据库与备份实例（长名称可读性验证）',{'resource_kind':'PostgreSQL','region':'华东','environment':'测试'}),
          ('domain','对外服务 · example.test',{'domain_name':'example.test','registrar':'合成验收注册商','expires_on':'2026-11-01'})]:
            fields={'name':name,'provider_name':'合成验收','purpose':'用于第三阶段界面验收，不代表真实生产资产','attributes':attrs,'platform_id':platform['id']}
            if kind in {'platform_account','mailbox_account'}:fields['account']={'identifier':'synthetic@example.test','login_methods':['password'],'account_role':'master'}
            row=resource(env,kind,**fields)
            row=created(post(env.admin,f"/resources/{row['id']}/actions/initial-facts",{'expected_version':row['version'],'people':[{'person_id':admin_id,'role':'owner'}],'company_links':[{'company_id':company['id'],'role':'owner'}],'source_note':'合成验收初始核实'}))
            row=created(post(env.admin,f"/resources/{row['id']}/actions/confirm-lifecycle",{'expected_version':row['version'],'lifecycle':'in_use','reason':'合成验收中的使用状态'}))
            resources.append(row)
        manager,manager_account=env.member('v3-reviewer','resource_manager',[{'kind':'resource','target_id':r['id'],'permission':'manage'} for r in resources])
        member,member_account=env.member('v3-member','member',[{'kind':'resource','target_id':resources[0]['id'],'permission':'read'}])
        private=resource(env,'application',name='管理员私有 · 隐藏验收对象')
        current=created(env.admin.get('/api/v1/resources/'+resources[5]['id']))
        created(post(env.admin,f"/resources/{current['id']}/relations",{'expected_version':current['version'],'target_id':resources[7]['id'],'relation_type':'depends_on','note':'合成应用依赖合成数据库'}))
        created(post(env.admin,f"/resources/{resources[0]['id']}/materials",{'kind':'entry','title':'进入平台工作区','url':'https://example.test/workspace'}))
        evidence=created(post(env.admin,f"/resources/{resources[0]['id']}/materials",{'kind':'note','title':'合成验收 · 实际执行记录','body':'已在隔离验收场景核对使用人。此记录是合成证据。'}))
        r=created(env.admin.get('/api/v1/resources/'+resources[0]['id']))
        stage=created(post(env.admin,f"/resources/{r['id']}/secret-stages",{'kind':'api_key','secret_value':'synthetic-stage3-fixture-not-a-real-api-key','purpose':'attach'}))
        credential=created(post(env.admin,f"/resources/{r['id']}/credentials",{'expected_version':r['version'],'kind':'api_key','stage_token':stage['stage_token']}))['safe_result']['credential_id']
        metadata=created(env.admin.get(f"/api/v1/resources/{r['id']}/credentials"))['items'][0]
        created(post(env.admin,f'/credentials/{credential}/grants',{'person_id':admin_id,'capability':'view','reason':'合成凭据授权查看验收','expected_version':metadata['version'],'valid_to':(datetime.now(UTC)+timedelta(days=1)).isoformat()}))
        connection=created(post(env.admin,'/platform-connections',{'resource_id':r['id'],'credential_id':credential,'label':'合成验收 · DeepSeek 余额连接','scheduled':False}))
        with Session(env.engine) as db:
            successful=SyncJob(resource_id=UUID(r['id']),connection_id=UUID(connection['id']),status='succeeded',dedupe_key='synthetic-browser-success',attempts=1,available_at=datetime.now(UTC)-timedelta(days=2),finished_at=datetime.now(UTC)-timedelta(days=2))
            db.add(successful);db.flush()
            db.add(MetricSnapshot(job_id=successful.id,resource_id=UUID(r['id']),connection_id=UUID(connection['id']),currency='CNY',total_balance='88.50',granted_balance='8.50',topped_up_balance='80.00',is_available=True,collected_at=datetime.now(UTC)-timedelta(days=2)))
            db.add(SyncJob(resource_id=UUID(r['id']),connection_id=UUID(connection['id']),status='failed',dedupe_key='synthetic-browser-fixture',attempts=3,last_error_code='UPSTREAM_TIMEOUT',available_at=datetime.now(UTC)-timedelta(days=1),finished_at=datetime.now(UTC)-timedelta(days=1)))
            conn=db.get(PlatformConnection,UUID(connection['id']));conn.last_success_at=datetime.now(UTC)-timedelta(days=2);conn.last_attempt_at=datetime.now(UTC)-timedelta(days=1);conn.last_error_code='UPSTREAM_TIMEOUT';db.commit()
        ledger=created(post(env.admin,'/subscriptions',{'resource_id':resources[3]['id'],'plan':'合成年度套餐','seats_total':20,'seats_assigned':8,'billing_cycle':'year','reminder_days':[30,7,1]}))
        created(post(env.admin,f"/subscriptions/{ledger['id']}/periods",{'expected_version':ledger['version'],'starts_on':'2026-10-01','ends_on':'2026-11-01','planned_amount':'1200.00','currency':'CNY','source':'合成验收合同'}))
        for currency,amount in [('CNY','800.00'),('USD','30.00')]:
            ledger=created(env.admin.get('/api/v1/subscriptions/'+ledger['id']))
            created(post(env.admin,f"/subscriptions/{ledger['id']}/expenses",{'expected_version':ledger['version'],'amount':amount,'currency':currency,'kind':'actual','recorded_on':'2026-10-18','source':'合成验收费用凭证'}))
        created(post(env.admin,'/reminders/actions/refresh'))
        case=created(post(env.admin,'/change-cases',{'case_type':'change','reason':'合成验收 · 授予团队成员使用账号','coordinator_person_id':admin_id}))
        item=created(post(env.admin,f"/change-cases/{case['id']}/items",{'resource_id':r['id'],'assignee_person_id':manager_account['person_id'],'proposal':{'action':'grant_use','person_id':member_account['person_id']}}))
        case=created(env.admin.get('/api/v1/change-cases/'+case['id']))
        created(post(env.admin,f"/change-cases/{case['id']}/actions/submit",{'expected_version':case['version']}))
        if '--large-map' in sys.argv:
            with Session(env.engine) as db:
                for i in range(105):
                    target=Resource(id=uuid4(),code=f'SYNTHETIC-MAP-{i:03}',name=f'合成边界节点 {i:03} · 长名称云资源',type_code='cloud_resource',created_by_person_id=UUID(admin_id))
                    db.add(target);db.flush()
                    db.add(ResourceRelation(source_resource_id=UUID(resources[5]['id']),target_resource_id=target.id,relation_type='depends_on',confirmation='proposed'))
                db.commit()
        report={'database':env.settings.expected_database,'synthetic':True,'large_map_fixture':'--large-map' in sys.argv,'resources':[{k:x[k] for k in ('id','name','type_code')} for x in resources],'case_id':case['id'],'item_id':item['id'],'evidence_id':evidence['id'],'connection_id':connection['id'],'ledger_id':ledger['id'],'hidden_resource_id':private['id'],'accounts':['stage-admin','v3-reviewer','v3-member'],'password_note':'Synthetic test fixture PASSWORD from test_local_identity; never a real account password.'}
        (root/'.local/workspace/stage3-browser-fixture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Created isolated synthetic browser fixture; 3 roles; large map:', '--large-map' in sys.argv, '. No external platform request.')
    finally:
        generator.close()

if __name__=='__main__':main()
