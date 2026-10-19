from datetime import datetime
from typing import Annotated,Literal
from uuid import UUID
from fastapi import APIRouter,Depends,Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.identity_access.public import require_capability,has_login_account
from app.modules.resources.public import person_has_current_roles
from app.platform.db.models import Person,Department,AuthAccount,ResourcePerson,ContactIdentity,AccountBinding,MailboxContactAssociation
from app.platform.db.commands import actor,now,record_event,require_idempotency_key
from app.platform.db.session import database_session
from app.platform.http.schemas import StrictModel,SuccessEnvelope,ResponseMeta
from app.platform.http.errors import ApiException

router=APIRouter(tags=['directory'])
DB=Annotated[Session,Depends(database_session)]
Admin=Annotated[object,Depends(require_capability('directory.manage'))]
Catalog=Annotated[object,Depends(require_capability('catalog.write'))]
Read=Annotated[object,Depends(require_capability('directory.read'))]
KEY=[Depends(require_idempotency_key)]

class PersonCreate(StrictModel):
    display_name:str=Field(min_length=1,max_length=200)
    department_id:UUID|None=None
    status:Literal['active','inactive','unknown']='active'

class PersonPatch(PersonCreate):
    expected_version:int=Field(ge=1)

class PersonView(StrictModel):
    id:UUID
    display_name:str
    department_id:UUID|None
    status:str
    version:int

class IdentityPatch(StrictModel):
    expected_version:int=Field(ge=1)
    label:str|None=Field(default=None,max_length=200)
    provider:str|None=Field(default=None,max_length=200)

class IdentityMetadata(StrictModel):
    id:UUID
    label:str|None
    provider:str|None
    version:int

def env(request,data):return SuccessEnvelope(data=data,error=None,meta=ResponseMeta(request_id=request.state.request_id))
def validate_person(session,payload):
    if not payload.display_name.strip():raise ApiException(422,'VALIDATION_FAILED','姓名不能为空')
    if payload.department_id and not session.get(Department,payload.department_id):raise ApiException(404,'REFERENCE_NOT_FOUND','部门不存在或不可见')

@router.post('/people',response_model=SuccessEnvelope[PersonView],status_code=201,operation_id='createDirectoryPerson',dependencies=KEY)
def create(payload:PersonCreate,request:Request,_:Admin,session:DB):
    validate_person(session,payload);row=Person(**payload.model_dump());row.display_name=row.display_name.strip();session.add(row);session.flush()
    record_event(session,'directory.person_created',actor(request),request.state.request_id,data={'person_id':str(row.id)})
    session.commit();return env(request,PersonView.model_validate(row,from_attributes=True))

@router.get('/people/{person_id}',response_model=SuccessEnvelope[PersonView],operation_id='getDirectoryPerson')
def get(person_id:UUID,request:Request,_:Read,session:DB):
    row=session.get(Person,person_id)
    if not row:raise ApiException(404,'RESOURCE_NOT_FOUND','人员不存在或不可见')
    return env(request,PersonView.model_validate(row,from_attributes=True))

@router.patch('/people/{person_id}',response_model=SuccessEnvelope[PersonView],operation_id='patchDirectoryPerson',dependencies=KEY)
def patch(person_id:UUID,payload:PersonPatch,request:Request,_:Admin,session:DB):
    validate_person(session,payload);row=session.scalar(select(Person).where(Person.id==person_id).with_for_update())
    if not row:raise ApiException(404,'RESOURCE_NOT_FOUND','人员不存在或不可见')
    if has_login_account(session,person_id):raise ApiException(409,'AUTH_ACCOUNT_MANAGED','登录人员请通过团队账号接口维护')
    if row.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','人员已更新')
    if payload.status!='active' and person_has_current_roles(session,person_id):raise ApiException(409,'GOVERNANCE_REQUIRED','请先处理有效业务角色及交接')
    for field in payload.model_fields_set-{'expected_version'}:setattr(row,field,getattr(payload,field))
    row.display_name=row.display_name.strip();row.version+=1;row.updated_at=now()
    record_event(session,'directory.person_updated',actor(request),request.state.request_id,data={'person_id':str(row.id)})
    session.commit();return env(request,PersonView.model_validate(row,from_attributes=True))

@router.patch('/contact-identities/{identity_id}',response_model=SuccessEnvelope[IdentityMetadata],operation_id='patchContactIdentityMetadata',dependencies=KEY)
def patch_identity(identity_id:UUID,payload:IdentityPatch,request:Request,_:Catalog,session:DB):
    row=session.scalar(select(ContactIdentity).where(ContactIdentity.id==identity_id).with_for_update())
    if not row:raise ApiException(404,'RESOURCE_NOT_FOUND','身份不存在或不可见')
    principal=session.info.get('local_principal')
    if principal and principal.role!='admin' and row.created_by_person_id!=principal.person_id:raise ApiException(403,'PERMISSION_DENIED','仅创建人或管理员可修订身份备注')
    if row.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','身份已更新')
    if not payload.model_fields_set-{'expected_version'}:raise ApiException(422,'VALIDATION_FAILED','需要修改内容')
    if 'provider' in payload.model_fields_set and row.kind=='third_party' and not payload.provider:raise ApiException(422,'VALIDATION_FAILED','第三方身份的平台不能清空')
    for field in payload.model_fields_set-{'expected_version'}:setattr(row,field,getattr(payload,field))
    row.version+=1;row.updated_at=now()
    record_event(session,'directory.identity_metadata_updated',actor(request),request.state.request_id,data={'identity_id':str(row.id)})
    session.commit();return env(request,IdentityMetadata.model_validate(row,from_attributes=True))
