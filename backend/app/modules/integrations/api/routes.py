from datetime import timedelta
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,Query,Request
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.modules.identity_access.public import require_capability
from app.modules.integrations.api.schemas import *
from app.modules.integrations.application import service
from app.platform.db.models import PlatformConnection,SyncJob,MetricSnapshot,WorkerHeartbeat
from app.platform.db.session import database_session
from app.platform.db.commands import actor,require_idempotency_key,now
from app.platform.http.schemas import SuccessEnvelope,ResponseMeta

router=APIRouter(tags=['integrations'])
DB=Annotated[Session,Depends(database_session)]
Manage=Annotated[object,Depends(require_capability('integration.manage'))]
Grant=Annotated[object,Depends(require_capability('credential.grant'))]
Read=Annotated[object,Depends(require_capability('finance.read'))]
Admin=Annotated[object,Depends(require_capability('identity.manage'))]
KEY=[Depends(require_idempotency_key)]


def env(request,data):return SuccessEnvelope(data=data,error=None,meta=ResponseMeta(request_id=request.state.request_id))


def paged(session,model,page,page_size,conditions=()):
    stmt=select(model).where(*conditions);total=session.scalar(select(func.count()).select_from(stmt.subquery()))
    return session.scalars(stmt.order_by(model.id).offset((page-1)*page_size).limit(page_size)).all(),dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)


@router.get('/integration-providers',response_model=SuccessEnvelope[ProviderPage],operation_id='listIntegrationProviders')
def providers(request:Request,_:Manage):return env(request,ProviderPage(items=[ProviderCapability()]))


@router.post('/platform-connections',response_model=SuccessEnvelope[ConnectionView],status_code=201,operation_id='createPlatformConnection',dependencies=KEY)
def create(payload:ConnectionCreate,request:Request,_:Manage,_grant:Grant,session:DB):return env(request,service.connection_view(service.create_connection(session,payload,actor(request),request.state.request_id)))


@router.patch('/platform-connections/{connection_id}',response_model=SuccessEnvelope[ConnectionView],operation_id='patchPlatformConnection',dependencies=KEY)
def patch(connection_id:UUID,payload:ConnectionPatch,request:Request,_:Manage,_grant:Grant,session:DB):return env(request,service.connection_view(service.patch_connection(session,connection_id,payload,actor(request),request.state.request_id)))


@router.get('/platform-connections',response_model=SuccessEnvelope[ConnectionPage],operation_id='listPlatformConnections')
def listing(request:Request,_:Manage,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    rows,pagination=paged(session,PlatformConnection,page,page_size)
    return env(request,ConnectionPage(items=[service.connection_view(x) for x in rows],pagination=pagination))


@router.post('/platform-connections/{connection_id}/actions/sync',response_model=SuccessEnvelope[JobView],status_code=202,operation_id='requestPlatformSync',dependencies=KEY)
def sync(connection_id:UUID,request:Request,_:Manage,session:DB):
    job=service.enqueue(session,connection_id,'manual:'+request.headers['idempotency-key'],actor(request),request.state.request_id)
    session.commit();return env(request,JobView.model_validate(job,from_attributes=True))


@router.post('/platform-connections/{connection_id}/actions/test',response_model=SuccessEnvelope[JobView],status_code=202,operation_id='testPlatformConnection',dependencies=KEY)
def test(connection_id:UUID,request:Request,_:Manage,session:DB):
    job=service.enqueue(session,connection_id,'test:'+request.headers['idempotency-key'],actor(request),request.state.request_id)
    session.commit();return env(request,JobView.model_validate(job,from_attributes=True))


@router.get('/sync-jobs',response_model=SuccessEnvelope[JobPage],operation_id='listSyncJobs')
def jobs(request:Request,_:Manage,session:DB,connection_id:UUID|None=None,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    rows,pagination=paged(session,SyncJob,page,page_size,[SyncJob.connection_id==connection_id] if connection_id else [])
    return env(request,JobPage(items=[JobView.model_validate(x,from_attributes=True) for x in rows],pagination=pagination))


@router.get('/metric-snapshots',response_model=SuccessEnvelope[SnapshotPage],operation_id='listMetricSnapshots')
def snapshots(request:Request,_:Read,session:DB,connection_id:UUID|None=None,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    rows,pagination=paged(session,MetricSnapshot,page,page_size,[MetricSnapshot.connection_id==connection_id] if connection_id else [])
    return env(request,SnapshotPage(items=[SnapshotView.model_validate(x,from_attributes=True) for x in rows],pagination=pagination))


@router.get('/integration-worker',response_model=SuccessEnvelope[WorkerStatus],operation_id='getIntegrationWorkerStatus')
def worker_status(request:Request,_:Admin,session:DB):
    seen=session.scalar(select(func.max(WorkerHeartbeat.seen_at)))
    counts=dict(session.execute(select(SyncJob.status,func.count()).group_by(SyncJob.status)).all())
    return env(request,WorkerStatus(counts=counts,last_seen_at=seen,recent_heartbeat=bool(seen and now()-seen<timedelta(seconds=90))))
