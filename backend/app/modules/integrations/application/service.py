from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select,func,or_,and_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.modules.credentials.public import read_connection_secret,cleanup_ephemeral_credentials
from app.modules.subscriptions.public import refresh_reminders
from app.modules.provenance.public import cleanup_expired_imports
from app.modules.integrations.application.deepseek import fetch_balances,AdapterError
from app.platform.db.models import PlatformConnection,SyncJob,MetricSnapshot,CredentialRef,Resource,AuditEvent,WorkerHeartbeat
from app.platform.db.commands import now,write_resource,record_event
from app.platform.http.errors import ApiException


def connection_view(row):
    from app.modules.integrations.api.schemas import ConnectionView
    data=ConnectionView.model_validate({k:getattr(row,k) for k in ConnectionView.model_fields if k!='stale'}|{'stale':row.last_success_at is None or row.last_error_code is not None or (now()-row.last_success_at).total_seconds()>row.interval_seconds*2})
    return data


def credential_for_connection(session,resource_id,credential_id):
    ref=session.get(CredentialRef,credential_id)
    if not ref or ref.resource_id!=resource_id or ref.kind!='api_key' or ref.status!='saved':raise ApiException(404,'REFERENCE_NOT_FOUND','连接需要同一资源下有效的API凭据')
    return ref


def create_connection(session,payload,actor_id,request_id):
    write_resource(session,payload.resource_id)
    ref=credential_for_connection(session,payload.resource_id,payload.credential_id)
    connection=PlatformConnection(**payload.model_dump(),credential_version=ref.version,created_by_person_id=actor_id,next_run_at=now() if payload.scheduled else None)
    session.add(connection);session.flush()
    record_event(session,'integration.server_use_authorized',actor_id,request_id,connection.resource_id,{'connection_id':str(connection.id),'credential_id':str(ref.id),'version':ref.version})
    session.commit();return connection


def get_connection(session,connection_id,writing=False):
    row=session.get(PlatformConnection,connection_id)
    if not row:raise ApiException(404,'RESOURCE_NOT_FOUND','连接不存在或不可见')
    if writing:
        write_resource(session,row.resource_id)
        row=session.scalar(select(PlatformConnection).where(PlatformConnection.id==connection_id).with_for_update().execution_options(populate_existing=True))
    return row


def patch_connection(session,connection_id,payload,actor_id,request_id):
    row=get_connection(session,connection_id,True)
    if row.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','连接已更新')
    if not payload.model_fields_set-{'expected_version'}:raise ApiException(422,'VALIDATION_FAILED','需要修改内容')
    if payload.credential_id:
        ref=credential_for_connection(session,row.resource_id,payload.credential_id)
        row.credential_id,row.credential_version=ref.id,ref.version
        row.last_error_code='RETEST_REQUIRED'
    for field in ('status','scheduled','interval_seconds'):
        if field in payload.model_fields_set:
            value=getattr(payload,field)
            if value is None:raise ApiException(422,'VALIDATION_FAILED','连接配置不能清空')
            setattr(row,field,value)
    row.next_run_at=now() if row.scheduled and row.status=='active' else None
    row.version+=1
    if row.status=='inactive':
        for job in session.scalars(select(SyncJob).where(SyncJob.connection_id==row.id,SyncJob.status.in_(['pending','running']))):job.status='cancelled';job.finished_at=now()
    record_event(session,'integration.connection_updated',actor_id,request_id,row.resource_id,{'connection_id':str(row.id),'status':row.status})
    session.commit();return row


def enqueue(session,connection_id,dedupe_key,actor_id=None,request_id=None):
    connection=get_connection(session,connection_id,actor_id is not None)
    if connection.status!='active':raise ApiException(409,'CONNECTION_INACTIVE','连接未启用')
    ref=credential_for_connection(session,connection.resource_id,connection.credential_id)
    if ref.version!=connection.credential_version:raise ApiException(409,'CONNECTION_CREDENTIAL_CHANGED','凭据版本已变化，请重新授权连接')
    existing=session.scalar(select(SyncJob).where(SyncJob.connection_id==connection.id,SyncJob.dedupe_key==dedupe_key))
    if existing:return existing
    job=SyncJob(connection_id=connection.id,resource_id=connection.resource_id,dedupe_key=dedupe_key,available_at=now())
    session.add(job);session.flush()
    if actor_id:record_event(session,'integration.job_requested',actor_id,request_id,connection.resource_id,{'job_id':str(job.id)})
    return job


def schedule_due(session,instant):
    rows=session.scalars(select(PlatformConnection).where(PlatformConnection.status=='active',PlatformConnection.scheduled.is_(True),or_(PlatformConnection.next_run_at.is_(None),PlatformConnection.next_run_at<=instant)).with_for_update(skip_locked=True).limit(100)).all()
    for row in rows:
        key='schedule:'+str(int(instant.timestamp())//row.interval_seconds)
        try:enqueue(session,row.id,key)
        except ApiException as error:
            row.last_error_code=error.code;row.scheduled=False
        row.next_run_at=instant+timedelta(seconds=row.interval_seconds)
    return len(rows)


def run_once(engine,settings,*,fetcher=None,worker_id='local-worker',instant=None,target_job_id=None):
    instant=instant or now();fetcher=fetcher or fetch_balances
    with Session(engine) as session:
        session.execute(insert(WorkerHeartbeat).values(id=worker_id,seen_at=instant).on_conflict_do_update(index_elements=['id'],set_={'seen_at':instant}))
        schedule_due(session,instant)
        refresh_reminders(session,instant)
        cleanup_ephemeral_credentials(session,instant)
        cleanup_expired_imports(session,instant)
        for exhausted in session.scalars(select(SyncJob).where(SyncJob.status=='running',SyncJob.lease_until<instant,SyncJob.attempts>=3).with_for_update(skip_locked=True)):
            exhausted.status='failed';exhausted.last_error_code='LEASE_EXHAUSTED';exhausted.finished_at=instant
        session.commit()
    with Session(engine) as session:
        statement=select(SyncJob).where(SyncJob.attempts<3,or_(and_(SyncJob.status=='pending',SyncJob.available_at<=instant),and_(SyncJob.status=='running',SyncJob.lease_until<instant)))
        if target_job_id:statement=statement.where(SyncJob.id==target_job_id)
        job=session.scalar(statement.order_by(SyncJob.available_at,SyncJob.id).with_for_update(skip_locked=True).limit(1))
        if not job:return {'processed':False}
        job.status='running';job.attempts+=1;job.lease_token=uuid4();job.lease_until=instant+timedelta(seconds=120)
        job_id,lease=job.id,job.lease_token
        session.commit()
    error=None;balances=None
    try:
        with Session(engine) as session:
            job=session.get(SyncJob,job_id);connection=session.get(PlatformConnection,job.connection_id)
            resource=session.get(Resource,job.resource_id)
            if not connection or connection.status!='active' or not resource or resource.archived_at or resource.lifecycle in {'disabled','retired'}:raise AdapterError('RESOURCE_OR_CONNECTION_INACTIVE')
            credential_id,version=connection.credential_id,connection.credential_version
            secret=read_connection_secret(session,settings,connection.resource_id,connection.credential_id,version)
        balances=fetcher(secret)
    except AdapterError as failure:error=failure
    except ApiException as failure:error=AdapterError(failure.code)
    except Exception:error=AdapterError('WORKER_DEPENDENCY_FAILURE',True)
    with Session(engine) as session:
        connection_id=session.scalar(select(SyncJob.connection_id).where(SyncJob.id==job_id))
        connection=session.scalar(select(PlatformConnection).where(PlatformConnection.id==connection_id).with_for_update())
        job=session.scalar(select(SyncJob).where(SyncJob.id==job_id).with_for_update().execution_options(populate_existing=True))
        if job.status!='running' or job.lease_token!=lease:return {'processed':True,'discarded_stale_lease':True}
        credential=session.get(CredentialRef,connection.credential_id)
        resource=session.get(Resource,connection.resource_id)
        if connection.status!='active' or not resource or resource.archived_at or resource.lifecycle in {'disabled','retired'} or not credential or credential.status!='saved' or credential.version!=connection.credential_version or (balances is not None and (connection.credential_version!=version or connection.credential_id!=credential_id)):error=AdapterError('CONNECTION_CREDENTIAL_CHANGED')
        connection.last_attempt_at=now()
        if error:
            job.last_error_code=connection.last_error_code=error.code
            if error.retryable and job.attempts<3:
                job.status='pending';job.available_at=now()+timedelta(seconds=error.retry_after or 30*2**(job.attempts-1))
            else:job.status='failed';job.finished_at=now()
        else:
            for balance in balances:session.add(MetricSnapshot(resource_id=connection.resource_id,connection_id=connection.id,job_id=job.id,**balance.__dict__))
            connection.last_success_at=now();connection.last_error_code=None
            job.status='succeeded';job.finished_at=now();job.last_error_code=None
        job.lease_until=None;job.lease_token=None
        session.add(AuditEvent(resource_id=connection.resource_id,actor_kind='system',event_type='integration.job_finished',request_id=uuid4(),safe_after={'job_id':str(job.id),'status':job.status,'error_code':job.last_error_code}))
        session.commit();return {'processed':True,'status':job.status,'error_code':job.last_error_code}


def deactivate_resource_connections(session,resource_id):
    for connection in session.scalars(select(PlatformConnection).where(PlatformConnection.resource_id==resource_id,PlatformConnection.status=='active')):
        connection.status='inactive';connection.scheduled=False;connection.version+=1
    for job in session.scalars(select(SyncJob).where(SyncJob.resource_id==resource_id,SyncJob.status.in_(['pending','running']))):job.status='cancelled';job.finished_at=now()
