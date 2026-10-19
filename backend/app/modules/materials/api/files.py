from datetime import datetime
from typing import Annotated,Literal
from uuid import UUID
from fastapi import APIRouter,Depends,Request,Body,Query
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.platform.http.schemas import StrictModel,SuccessEnvelope,ResponseMeta
from app.platform.db.session import database_session
from app.platform.db.commands import actor,require_idempotency_key,record_event
from app.platform.db.models import PrivateFile
from app.platform.http.errors import ApiException
from app.modules.identity_access.public import require_capability
from app.modules.materials.application.files import upload,available_file,binary_path,end_file
from app.modules.materials.api.schemas import MaterialPatchRequest
from app.modules.resources.public import get_resource

router=APIRouter(tags=['files'])
DB=Annotated[Session,Depends(database_session)]
Read=Annotated[object,Depends(require_capability('materials.read'))]
Write=Annotated[object,Depends(require_capability('materials.write'))]
KEY=[Depends(require_idempotency_key)]

class FileView(StrictModel):
    id:UUID
    resource_id:UUID
    filename:str
    media_type:str
    size_bytes:int
    status:Literal['available','replaced','ended']
    classification:Literal['normal','restricted','sensitive']
    check_policy:str
    replaces_file_id:UUID|None
    version:int
    created_at:datetime
    ended_at:datetime|None

class FilePage(StrictModel):
    items:list[FileView]
    pagination:dict[str,int|bool]

class EndFile(StrictModel):
    expected_version:int=Field(ge=1)
    reason:str=Field(min_length=1,max_length=2000)

def env(request,data):return SuccessEnvelope(data=data,error=None,meta=ResponseMeta(request_id=request.state.request_id))
def view(row):return FileView.model_validate(row,from_attributes=True)

@router.post('/files',response_model=SuccessEnvelope[FileView],status_code=201,operation_id='uploadPrivateFile',dependencies=KEY)
def create(request:Request,_:Write,session:DB,resource_id:UUID,filename:str=Query(min_length=1,max_length=200),classification:Literal['normal','restricted','sensitive']='normal',replaces_file_id:UUID|None=None,expected_version:int|None=Query(None,ge=1),body:bytes=Body(media_type='application/octet-stream')):
    return env(request,view(upload(session,request.app.state.settings,resource_id,filename,body,classification,actor(request),request.state.request_id,replaces_file_id,expected_version)))

@router.get('/resources/{resource_id}/files',response_model=SuccessEnvelope[FilePage],operation_id='listResourceFiles')
def listing(resource_id:UUID,request:Request,_:Read,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    get_resource(session,resource_id)
    stmt=select(PrivateFile).where(PrivateFile.resource_id==resource_id)
    total=session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=session.scalars(stmt.order_by(PrivateFile.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return env(request,FilePage(items=[view(x) for x in rows],pagination=dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)))

@router.get('/files/{file_id}',response_model=SuccessEnvelope[FileView],operation_id='getPrivateFileMetadata')
def metadata(file_id:UUID,request:Request,_:Read,session:DB):return env(request,view(available_file(session,file_id)))

@router.get('/files/{file_id}/content',response_class=FileResponse,operation_id='downloadPrivateFile')
def download(file_id:UUID,request:Request,_:Read,session:DB):
    row=available_file(session,file_id);path=binary_path(request.app.state.settings,row.storage_key)
    if not path.is_file():raise ApiException(503,'DEPENDENCY_UNAVAILABLE','附件数据暂不可读')
    record_event(session,'file.downloaded',actor(request),request.state.request_id,row.resource_id,{'file_id':str(file_id)})
    session.commit()
    return FileResponse(path,filename=row.filename,media_type='application/octet-stream',headers={'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

@router.post('/files/{file_id}/actions/end',response_model=SuccessEnvelope[FileView],operation_id='endPrivateFile',dependencies=KEY)
def end(file_id:UUID,payload:EndFile,request:Request,_:Write,session:DB):return env(request,view(end_file(session,file_id,payload,actor(request),request.state.request_id)))
