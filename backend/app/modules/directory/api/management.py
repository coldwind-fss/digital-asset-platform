from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, SecretStr, HttpUrl
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.modules.identity_access.public import require_capability
from app.modules.bindings.public import create_contact_identity
from app.platform.db.models import Company,Platform,ContactIdentity
from app.platform.db.session import database_session
from app.platform.db.commands import actor,now,record_event,require_idempotency_key
from app.platform.http.schemas import StrictModel,SuccessEnvelope,ResponseMeta
from app.platform.http.errors import ApiException

router=APIRouter(tags=["directory"])
DB=Annotated[Session,Depends(database_session)]
Write=Annotated[object,Depends(require_capability("catalog.write"))]
Read=Annotated[object,Depends(require_capability("directory.read"))]


class CompanyCreate(StrictModel):
    name: str=Field(min_length=1,max_length=200)
    registration_identifier: str|None=Field(default=None,max_length=200)
    description: str|None=Field(default=None,max_length=2000)


class PlatformCreate(StrictModel):
    name: str=Field(min_length=1,max_length=200)
    website: HttpUrl|None=None


class CatalogPatch(StrictModel):
    expected_version: int=Field(ge=1)
    name: str|None=Field(default=None,min_length=1,max_length=200)
    description: str|None=Field(default=None,max_length=2000)
    website: HttpUrl|None=None
    status: Literal["active","inactive","unknown"]|None=None


class IdentityCreate(StrictModel):
    kind: Literal["phone","email","third_party"]
    value: SecretStr=Field(min_length=1,max_length=320)
    label: str|None=Field(default=None,max_length=200)
    provider: str|None=Field(default=None,max_length=200)
    ownership: Literal["company","personal","unknown"]="unknown"
    company_id: UUID|None=None
    custodian_person_id: UUID|None=None


class CatalogView(StrictModel):
    id: UUID
    kind: Literal["company","platform","identity"]
    name: str
    status: str
    version: int
    website: str|None=None
    description: str|None=None
    registration_identifier: str|None=None
    identity_kind: str|None=None
    ownership: str|None=None
    masked_value: str|None=None
    company_id: UUID|None=None
    provider: str|None=None


class CatalogPage(StrictModel):
    items:list[CatalogView]
    pagination:dict[str,int|bool]


def view(row):
    if isinstance(row,Company):return CatalogView(id=row.id,kind="company",name=row.name,status=row.status,version=row.version,registration_identifier=row.registration_identifier,description=row.description)
    if isinstance(row,Platform):return CatalogView(id=row.id,kind="platform",name=row.name,status=row.status,version=row.version,website=row.website)
    return CatalogView(id=row.id,kind="identity",name=row.label or row.masked_value or "已保护身份",status=row.verification,version=row.version,identity_kind=row.kind,ownership=row.ownership,masked_value=row.masked_value,company_id=row.company_id,provider=row.provider)


def envelope(request,data):return SuccessEnvelope(data=data,error=None,meta=ResponseMeta(request_id=request.state.request_id))


def catalog_create(session,model,payload,request):
    name=payload.name.strip()
    if not name:raise ApiException(422,"VALIDATION_FAILED","名称不能为空")
    row=model(**{k:str(v) if k=="website" and v else v for k,v in payload.model_dump().items()})
    row.name=name
    session.add(row);session.flush()
    record_event(session,"catalog.created",actor(request),request.state.request_id,data={"id":str(row.id),"kind":model.__tablename__})
    session.commit();return envelope(request,view(row))


@router.post("/companies",response_model=SuccessEnvelope[CatalogView],status_code=201,operation_id="createCompany",dependencies=[Depends(require_idempotency_key)])
def create_company(request:Request,payload:CompanyCreate,_:Write,session:DB):return catalog_create(session,Company,payload,request)


@router.post("/platforms",response_model=SuccessEnvelope[CatalogView],status_code=201,operation_id="createPlatform",dependencies=[Depends(require_idempotency_key)])
def create_platform(request:Request,payload:PlatformCreate,_:Write,session:DB):return catalog_create(session,Platform,payload,request)


@router.post("/contact-identities",response_model=SuccessEnvelope[CatalogView],status_code=201,operation_id="createContactIdentity",dependencies=[Depends(require_idempotency_key)])
def create_identity(request:Request,payload:IdentityCreate,_:Write,session:DB):
    data=payload.model_dump(exclude={"value"});data["value"]=payload.value.get_secret_value()
    row=create_contact_identity(session,**data)
    record_event(session,"identity.created",actor(request),request.state.request_id,data={"identity_id":str(row.id)})
    session.commit();return envelope(request,view(row))


@router.get("/platforms",response_model=SuccessEnvelope[CatalogPage],operation_id="listPlatforms")
def platforms(request:Request,_:Read,session:DB,q:str|None=Query(None,max_length=100),page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    stmt=select(Platform)
    if q:stmt=stmt.where(Platform.name.ilike('%'+q+'%'))
    total=session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=session.scalars(stmt.order_by(Platform.name,Platform.id).offset((page-1)*page_size).limit(page_size)).all()
    return envelope(request,CatalogPage(items=[view(x) for x in rows],pagination=dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)))


@router.get("/contact-identities",response_model=SuccessEnvelope[CatalogPage],operation_id="listContactIdentities")
def identities(request:Request,_:Read,session:DB,q:str|None=Query(None,max_length=100),page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    stmt=select(ContactIdentity)
    if q:
        needle='%'+q.strip()+'%'
        stmt=stmt.where(or_(ContactIdentity.label.ilike(needle),ContactIdentity.masked_value.ilike(needle),ContactIdentity.provider.ilike(needle)))
    total=session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=session.scalars(stmt.order_by(ContactIdentity.created_at,ContactIdentity.id).offset((page-1)*page_size).limit(page_size)).all()
    return envelope(request,CatalogPage(items=[view(x) for x in rows],pagination=dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)))


KINDS={"company":Company,"platform":Platform,"identity":ContactIdentity}


@router.get("/directory/{kind}/{object_id}",response_model=SuccessEnvelope[CatalogView],operation_id="getDirectoryObject")
def detail(kind:Literal["company","platform","identity"],object_id:UUID,request:Request,_:Read,session:DB):
    row=session.get(KINDS[kind],object_id)
    if row is None:raise ApiException(404,"RESOURCE_NOT_FOUND","目录对象不存在或不可见")
    return envelope(request,view(row))


@router.patch("/directory/{kind}/{object_id}",response_model=SuccessEnvelope[CatalogView],operation_id="patchDirectoryObject",dependencies=[Depends(require_idempotency_key)])
def patch(kind:Literal["company","platform"],object_id:UUID,payload:CatalogPatch,request:Request,_:Write,session:DB):
    from app.modules.directory.application.catalog import update_catalog
    return envelope(request,view(update_catalog(session,kind,object_id,payload,actor(request),request.state.request_id)))
