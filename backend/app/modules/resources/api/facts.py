from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter,Depends,Query,Request
from pydantic import Field
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.modules.identity_access.public import require_capability
from app.modules.resources.application.facts import initial_facts,declare_relation,verify_fact,archive_fact
from app.modules.resources.api.schemas import PersonAssignmentCreate,CompanyLinkCreate,ResourceView,ResourcePage,ResourceType,Pagination
from app.modules.resources.api.routes import _view,_summary
from app.modules.resources.public import get_resource
from app.platform.db.models import RelationDeclaration,ProvenanceEntry,AuditEvent
from app.platform.db.session import database_session
from app.platform.db.commands import actor,require_idempotency_key
from app.platform.http.schemas import StrictModel,SuccessEnvelope,ResponseMeta

router=APIRouter(tags=["resources"])
DB=Annotated[Session,Depends(database_session)]
Read=Annotated[object,Depends(require_capability("resource.read"))]
Write=Annotated[object,Depends(require_capability("resource.write"))]
Confirm=Annotated[object,Depends(require_capability("governance.confirm"))]


class InitialFactsInput(StrictModel):
    expected_version:int=Field(ge=1)
    people:list[PersonAssignmentCreate]=Field(default_factory=list,max_length=200)
    company_links:list[CompanyLinkCreate]=Field(default_factory=list,max_length=100)
    source_note:str=Field(min_length=1,max_length=500)


class FactActionInput(StrictModel):
    expected_version:int=Field(ge=1)
    reason:str=Field(min_length=1,max_length=1000)
    lifecycle:Literal["unknown","in_use"]|None=None


class DeclarationInput(StrictModel):
    expected_version:int=Field(ge=1)
    relation_kind:Literal["managed_by","part_of","contains","depends_on","uses","platform","company","owner","registration","login","recovery","mfa"]
    state:Literal["unknown","not_applicable","verified_absent"]
    reason:str=Field(min_length=1,max_length=1000)
    source:str=Field(min_length=1,max_length=500)


class DeclarationView(StrictModel):
    id:UUID
    resource_id:UUID
    relation_kind:str
    state:str
    reason:str
    source:str
    ended_at:datetime|None
    created_at:datetime


class SourceView(StrictModel):
    id:UUID
    source_kind:str
    label:str
    source_ref:str|None
    created_at:datetime


class HistoryView(StrictModel):
    id:UUID
    event_type:str
    occurred_at:datetime
    actor_person_id:UUID|None
    safe_before:dict|None
    safe_after:dict|None


class DeclarationPage(StrictModel):
    items:list[DeclarationView]
    pagination:dict[str,int|bool]


class SourcePage(StrictModel):
    items:list[SourceView]
    pagination:dict[str,int|bool]


class HistoryPage(StrictModel):
    items:list[HistoryView]
    pagination:dict[str,int|bool]


def env(request,data):return SuccessEnvelope(data=data,error=None,meta=ResponseMeta(request_id=request.state.request_id))


@router.get("/resources/duplicate-candidates",response_model=SuccessEnvelope[ResourcePage],operation_id="findResourceDuplicateCandidates")
def duplicate_candidates(request:Request,_:Read,session:DB,name:str=Query(min_length=1,max_length=200),type_code:ResourceType|None=None,platform_id:UUID|None=None):
    from app.platform.db.models import Resource
    stmt=select(Resource).where(func.lower(Resource.name)==name.strip().lower(),Resource.archived_at.is_(None))
    if type_code:stmt=stmt.where(Resource.type_code==type_code.value)
    if platform_id:stmt=stmt.where(Resource.platform_id==platform_id)
    total=session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=session.scalars(stmt.order_by(Resource.id).limit(100)).all()
    return env(request,ResourcePage(items=[_summary(session,x) for x in rows],pagination=Pagination(page=1,page_size=100,total=total,has_next=total>100)))


@router.post("/resources/{resource_id}/actions/initial-facts",response_model=SuccessEnvelope[ResourceView],operation_id="setInitialResourceFacts",dependencies=[Depends(require_idempotency_key)])
def initial(resource_id:UUID,payload:InitialFactsInput,request:Request,_:Confirm,session:DB):
    row=initial_facts(session,resource_id,payload,actor(request),request.state.request_id)
    return env(request,_view(session,row))


@router.post("/resources/{resource_id}/relation-declarations",response_model=SuccessEnvelope[DeclarationView],status_code=201,operation_id="declareResourceRelation",dependencies=[Depends(require_idempotency_key)])
def declaration(resource_id:UUID,payload:DeclarationInput,request:Request,_:Write,session:DB):
    row=declare_relation(session,resource_id,payload,actor(request),request.state.request_id)
    return env(request,DeclarationView.model_validate(row,from_attributes=True))


def page_rows(session,model,resource_id,page,page_size):
    get_resource(session,resource_id)
    statement=select(model).where(model.resource_id==resource_id)
    total=session.scalar(select(func.count()).select_from(statement.subquery()))
    date_col=getattr(model,"created_at",None)
    if date_col is None:date_col=model.occurred_at
    rows=session.scalars(statement.order_by(date_col.desc(),model.id).offset((page-1)*page_size).limit(page_size)).all()
    return rows,dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)


@router.get("/resources/{resource_id}/relation-declarations",response_model=SuccessEnvelope[DeclarationPage],operation_id="listResourceDeclarations")
def declarations(resource_id:UUID,request:Request,_:Read,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    rows,pagination=page_rows(session,RelationDeclaration,resource_id,page,page_size)
    return env(request,DeclarationPage(items=[DeclarationView.model_validate(x,from_attributes=True) for x in rows],pagination=pagination))


@router.get("/resources/{resource_id}/sources",response_model=SuccessEnvelope[SourcePage],operation_id="listResourceSources")
def sources(resource_id:UUID,request:Request,_:Read,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    rows,pagination=page_rows(session,ProvenanceEntry,resource_id,page,page_size)
    return env(request,SourcePage(items=[SourceView.model_validate(x,from_attributes=True) for x in rows],pagination=pagination))


@router.get("/resources/{resource_id}/history",response_model=SuccessEnvelope[HistoryPage],operation_id="listResourceHistory")
def history(resource_id:UUID,request:Request,_:Read,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    rows,pagination=page_rows(session,AuditEvent,resource_id,page,page_size)
    return env(request,HistoryPage(items=[HistoryView.model_validate(x,from_attributes=True) for x in rows],pagination=pagination))


@router.post("/resources/{resource_id}/actions/verify",response_model=SuccessEnvelope[ResourceView],operation_id="verifyResource",dependencies=[Depends(require_idempotency_key)])
def verify(resource_id:UUID,payload:FactActionInput,request:Request,_:Confirm,session:DB):
    return env(request,_view(session,verify_fact(session,resource_id,payload,actor(request),request.state.request_id)))


@router.post("/resources/{resource_id}/actions/confirm-lifecycle",response_model=SuccessEnvelope[ResourceView],operation_id="confirmResourceLifecycle",dependencies=[Depends(require_idempotency_key)])
def lifecycle(resource_id:UUID,payload:FactActionInput,request:Request,_:Confirm,session:DB):
    return env(request,_view(session,verify_fact(session,resource_id,payload,actor(request),request.state.request_id,initial_lifecycle=True)))


@router.post("/resources/{resource_id}/actions/archive",response_model=SuccessEnvelope[ResourceView],operation_id="archiveResource",dependencies=[Depends(require_idempotency_key)])
def archive(resource_id:UUID,payload:FactActionInput,request:Request,_:Confirm,session:DB):
    return env(request,_view(session,archive_fact(session,resource_id,payload,actor(request),request.state.request_id,True)))


@router.post("/resources/{resource_id}/actions/unarchive",response_model=SuccessEnvelope[ResourceView],operation_id="unarchiveResource",dependencies=[Depends(require_idempotency_key)])
def unarchive(resource_id:UUID,payload:FactActionInput,request:Request,_:Confirm,session:DB):
    return env(request,_view(session,archive_fact(session,resource_id,payload,actor(request),request.state.request_id,False)))
