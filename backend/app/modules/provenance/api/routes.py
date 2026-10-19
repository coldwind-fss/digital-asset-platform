from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,Request,Query
from fastapi.responses import Response
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.modules.provenance.api.schemas import PreviewInput,CommitInput,BatchView,BatchPage
from app.modules.provenance.application import service
from app.modules.identity_access.public import require_capability
from app.platform.db.models import ImportBatch
from app.platform.db.session import database_session
from app.platform.db.commands import actor,require_idempotency_key,record_event
from app.platform.http.schemas import SuccessEnvelope,ResponseMeta

router=APIRouter(tags=['provenance'])
DB=Annotated[Session,Depends(database_session)]
Read=Annotated[object,Depends(require_capability('resource.read'))]
Write=Annotated[object,Depends(require_capability('resource.write'))]
KEY=[Depends(require_idempotency_key)]
def env(request,data):return SuccessEnvelope(data=data,error=None,meta=ResponseMeta(request_id=request.state.request_id))
def view(row):return BatchView.model_validate(row,from_attributes=True)
def csv_response(content,filename):return Response(content.encode('utf-8'),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{filename}"','X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

@router.get('/imports/template',response_class=Response,operation_id='getImportTemplate')
def template(_:Write,type_code:str=Query(pattern='^(platform_account|mailbox_account|api_key|service_subscription|business_space|application|api_service|cloud_resource|domain)$')):
    headers=['name','provider_name','purpose','platform_id','source_note']
    if type_code=='domain':headers+=['domain_name','expires_on']
    if type_code in {'api_service','cloud_resource'}:headers+=['external_instance_id']
    return csv_response(service.csv_document(headers,[]),'resource-template.csv')

@router.post('/imports/preview',response_model=SuccessEnvelope[BatchView],status_code=201,operation_id='previewResourceImport',dependencies=KEY)
def preview(payload:PreviewInput,request:Request,_:Write,session:DB):return env(request,view(service.preview(session,payload,actor(request),request.state.request_id)))

@router.get('/imports',response_model=SuccessEnvelope[BatchPage],operation_id='listResourceImports')
def listing(request:Request,_:Write,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    stmt=select(ImportBatch);total=session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=session.scalars(stmt.order_by(ImportBatch.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return env(request,BatchPage(items=[view(x) for x in rows],pagination=dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)))

@router.get('/imports/{batch_id}',response_model=SuccessEnvelope[BatchView],operation_id='getResourceImport')
def get(batch_id:UUID,request:Request,_:Write,session:DB):return env(request,view(service.batch(session,batch_id)))

@router.post('/imports/{batch_id}/actions/commit',response_model=SuccessEnvelope[BatchView],operation_id='commitResourceImport',dependencies=KEY)
def commit(batch_id:UUID,payload:CommitInput,request:Request,_:Write,session:DB):return env(request,view(service.commit(session,batch_id,payload,actor(request),request.state.request_id)))

@router.get('/imports/{batch_id}/errors',response_class=Response,operation_id='getResourceImportErrors')
def errors(batch_id:UUID,_:Write,session:DB):
    batch=service.batch(session,batch_id)
    return csv_response(service.csv_document(['row_number','status','message'],[(x['row_number'],x['status'],x.get('message')) for x in batch.results if x['status'] in {'error','duplicate_candidate'}]),'import-errors.csv')

@router.get('/exports/resources',response_class=Response,operation_id='exportResourceCsv')
def export(request:Request,_:Read,session:DB):
    content=service.export_resources(session);record_event(session,'resource.exported',actor(request),request.state.request_id);session.commit()
    return csv_response(content,'resources.csv')
