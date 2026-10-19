from datetime import datetime
from typing import Annotated,Literal
from uuid import UUID
from fastapi import APIRouter,Depends,Request,Query
from pydantic import Field,model_validator
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.modules.identity_access.public import require_capability
from app.modules.resources.public import get_resource
from app.modules.credentials.application.operations import prepare_operation
from app.modules.credentials.application.service import create_secret_stage
from app.modules.credentials.api.schemas import SecretStageCreate,SecretStageView,CredentialGrantView
from app.platform.db.models import CredentialRef,CredentialOperation,CredentialGrant
from app.platform.db.session import database_session
from app.platform.db.commands import actor
from app.platform.http.errors import ApiException
from app.platform.http.schemas import StrictModel,SuccessEnvelope,ResponseMeta

router=APIRouter(tags=["credentials"])
DB=Annotated[Session,Depends(database_session)]
Write=Annotated[object,Depends(require_capability("credential.write"))]
Read=Annotated[object,Depends(require_capability("resource.read"))]


class PrepareOperationInput(StrictModel):
    expected_version:int=Field(ge=1)
    action:Literal["replace","revoke","revoke_grant"]
    stage_token:str|None=Field(default=None,min_length=20,max_length=200,repr=False,json_schema_extra={"writeOnly":True})
    grant_id:UUID|None=None
    reason:str=Field(min_length=1,max_length=1000)

    @model_validator(mode="after")
    def validate_kind(self):
        if (self.action=="replace")!=(self.stage_token is not None):raise ValueError("替换操作必须且只能提供暂存令牌")
        if (self.action=="revoke_grant")!=(self.grant_id is not None):raise ValueError("撤销授权必须且只能提供授权ID")
        return self


class PreparedOperationView(StrictModel):
    id:UUID
    resource_id:UUID
    credential_id:UUID
    action:str
    status:str
    expires_at:datetime
    result_credential_id:UUID|None


class CredentialMetadata(StrictModel):
    id:UUID
    resource_id:UUID
    kind:str
    status:str
    version:int
    created_at:datetime


class CredentialMetadataPage(StrictModel):
    items:list[CredentialMetadata]
    pagination:dict[str,int|bool]


class CredentialGrantPage(StrictModel):
    items:list[CredentialGrantView]
    pagination:dict[str,int|bool]


def env(request,data):return SuccessEnvelope(data=data,error=None,meta=ResponseMeta(request_id=request.state.request_id))


@router.post("/resources/{resource_id}/secret-stages",response_model=SuccessEnvelope[SecretStageView],status_code=201,operation_id="createBoundSecretStage")
def bound_stage(resource_id:UUID,payload:SecretStageCreate,request:Request,_:Write,session:DB):
    if payload.resource_id not in {None,resource_id}:raise ApiException(422,"STAGE_TARGET_MISMATCH","路径和暂存目标不一致")
    stage,token=create_secret_stage(session,request.app.state.settings,payload.model_copy(update={"resource_id":resource_id}))
    return env(request,SecretStageView(stage_token=token,expires_at=stage.expires_at))


@router.post("/credentials/{credential_id}/operations",response_model=SuccessEnvelope[PreparedOperationView],status_code=201,operation_id="prepareCredentialOperation")
def prepare(credential_id:UUID,payload:PrepareOperationInput,request:Request,_:Write,session:DB):
    operation=prepare_operation(session,request.app.state.settings,credential_id,payload,actor(request),request.state.request_id)
    return env(request,PreparedOperationView.model_validate(operation,from_attributes=True))


@router.get("/credential-operations/{operation_id}",response_model=SuccessEnvelope[PreparedOperationView],operation_id="getCredentialOperation")
def operation_detail(operation_id:UUID,request:Request,_:Read,session:DB):
    row=session.get(CredentialOperation,operation_id)
    if not row:raise ApiException(404,"RESOURCE_NOT_FOUND","操作不存在或不可见")
    return env(request,PreparedOperationView.model_validate(row,from_attributes=True))


@router.get("/resources/{resource_id}/credentials",response_model=SuccessEnvelope[CredentialMetadataPage],operation_id="listCredentialMetadata")
def metadata(resource_id:UUID,request:Request,_:Read,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    get_resource(session,resource_id)
    stmt=select(CredentialRef).where(CredentialRef.resource_id==resource_id)
    total=session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=session.scalars(stmt.order_by(CredentialRef.created_at.desc(),CredentialRef.id).offset((page-1)*page_size).limit(page_size)).all()
    return env(request,CredentialMetadataPage(items=[CredentialMetadata.model_validate(x,from_attributes=True) for x in rows],pagination=dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)))


@router.get('/credentials/{credential_id}/grants',response_model=SuccessEnvelope[CredentialGrantPage],operation_id='listCredentialGrants')
def grants(credential_id:UUID,request:Request,_:Write,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    row=session.get(CredentialRef,credential_id)
    if not row:raise ApiException(404,'RESOURCE_NOT_FOUND','凭据不存在或不可见')
    stmt=select(CredentialGrant).where(CredentialGrant.credential_id==credential_id)
    total=session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=session.scalars(stmt.order_by(CredentialGrant.valid_from.desc(),CredentialGrant.id).offset((page-1)*page_size).limit(page_size)).all()
    return env(request,CredentialGrantPage(items=[CredentialGrantView.model_validate(x,from_attributes=True) for x in rows],pagination=dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)))
