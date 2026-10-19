"""One authorized read-only balance probe; never prints credentials or amounts."""
import argparse,json,re,sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime,UTC
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sqlalchemy import select,delete
from sqlalchemy.orm import Session
from app.config import Settings
from app.platform.db.target import create_database_engine,verify_database_identity
from app.platform.db.models import Resource,Person,CredentialRef,PlatformConnection,SyncJob,MetricSnapshot,AuditEvent
from app.modules.credentials.application.crypto import encrypt_secret
from app.modules.integrations.public import run_worker_once
from app.platform.db.commands import now


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--credential-file',required=True);args=parser.parse_args()
    settings=Settings.from_environment()
    if (settings.app_env,settings.expected_database,settings.instance_id)!=('test','digital_asset_platform_workspace_test','digital-asset-platform-workspace-test'):raise SystemExit('Live probe is restricted to the isolated workspace test database')
    raw=Path(args.credential_file).read_bytes()
    value=None
    for encoding in ('utf-8-sig','utf-16','gb18030'):
        try:value=raw.decode(encoding);break
        except UnicodeError:pass
    candidates=set(re.findall(r'sk-[A-Za-z0-9_-]{20,200}',value or ''))
    if len(candidates)!=1:raise SystemExit('Credential file must contain exactly one recognizable key')
    secret=candidates.pop();del raw,value,candidates
    engine=create_database_engine(settings);person_id,resource_id,credential_id,connection_id,job_id=[uuid4() for _ in range(5)]
    result={'provider':'deepseek','endpoint':'GET https://api.deepseek.com/user/balance','database':settings.expected_database,'checked_at':datetime.now(UTC).isoformat(),'read_only':True,'amounts_recorded_in_report':False}
    try:
        with engine.connect() as connection:verify_database_identity(connection,expected_database=settings.expected_database,expected_instance_id=settings.instance_id,expected_environment=settings.app_env)
        with Session(engine) as db:
            db.add(Person(id=person_id,display_name='Synthetic read-only connection probe',status='active'));db.flush()
            db.add(Resource(id=resource_id,code='probe-'+resource_id.hex,name='Synthetic DeepSeek balance verification',type_code='api_key',created_by_person_id=person_id));db.flush()
            encrypted=encrypt_secret(settings,secret,associated_data=f'credential:{credential_id}'.encode())
            db.add(CredentialRef(id=credential_id,resource_id=resource_id,kind='api_key',status='saved',ciphertext=encrypted.ciphertext,nonce=encrypted.nonce,key_version=encrypted.key_version));db.flush()
            db.add(PlatformConnection(id=connection_id,resource_id=resource_id,credential_id=credential_id,credential_version=1,provider='deepseek',label='Authorized read-only probe',created_by_person_id=person_id));db.flush()
            db.add(SyncJob(id=job_id,resource_id=resource_id,connection_id=connection_id,dedupe_key='authorized-live-probe',available_at=now()));db.commit()
        del secret
        outcome=run_worker_once(engine,settings,target_job_id=job_id,worker_id='authorized-live-probe')
        with Session(engine) as db:
            job=db.get(SyncJob,job_id);currencies=list(db.scalars(select(MetricSnapshot.currency).where(MetricSnapshot.job_id==job_id)))
            result.update(status=job.status,error_code=job.last_error_code,snapshot_count=len(currencies),currencies=currencies,encrypted_storage_verified=True)
    finally:
        with Session(engine) as db:
            for model in (MetricSnapshot,AuditEvent,SyncJob,PlatformConnection,CredentialRef):db.execute(delete(model).where(model.resource_id==resource_id))
            db.execute(delete(Resource).where(Resource.id==resource_id));db.execute(delete(Person).where(Person.id==person_id));db.commit()
        engine.dispose()
    result['probe_business_records_removed']=True
    report=ROOT.parent/'.local/workspace/deepseek-live-verification.json';report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result));return 0 if result.get('status')=='succeeded' else 1

if __name__=='__main__':raise SystemExit(main())
