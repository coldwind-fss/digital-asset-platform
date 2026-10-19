from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.modules.identity_access.public import require_capability, PolicySubject
from app.modules.resources.application.graph import local_graph
from app.platform.db.session import database_session
from app.platform.http.schemas import StrictModel, SuccessEnvelope, ResponseMeta

class GraphDeclaration(StrictModel):
    relation_kind: str
    state: Literal['unknown','not_applicable','verified_absent']

class GraphNode(StrictModel):
    id: UUID
    key: str
    kind: Literal['resource','company','platform','person','identity']
    label: str
    type_code: str
    verification: str
    lifecycle: str | None
    declarations: list[GraphDeclaration] = []

class GraphEdge(StrictModel):
    id: str
    source: str
    target: str
    relation: str
    confirmation: str

class LocalGraph(StrictModel):
    center: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool
    coverage: Literal['visible_known_relations']

router=APIRouter(tags=['resources'])

class ResourceRole(StrictModel):
    id: UUID
    resource_id: UUID
    resource_name: str
    person_id: UUID
    person_name: str
    role: str
    confirmation: str
    valid_from: str
    valid_to: str | None

class ResourceRolePage(StrictModel):
    items: list[ResourceRole]
    pagination: dict[str,int|bool]

@router.get('/resource-roles',response_model=SuccessEnvelope[ResourceRolePage],operation_id='listResourceRoles')
def roles(request:Request,_:Annotated[PolicySubject,Depends(require_capability('resource.read'))],session:Annotated[Session,Depends(database_session)],resource_id:UUID|None=None,person_id:UUID|None=None,role:Literal['owner','maintainer','controller','use']|None=None,q:str|None=Query(None,max_length=100),page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    from sqlalchemy import select,func,or_
    from app.platform.db.models import ResourcePerson,Resource,Person
    from app.platform.db.commands import now
    statement=select(ResourcePerson,Resource,Person).join(Resource,Resource.id==ResourcePerson.resource_id).join(Person,Person.id==ResourcePerson.person_id).where(Resource.archived_at.is_(None),ResourcePerson.valid_from<=now(),or_(ResourcePerson.valid_to.is_(None),ResourcePerson.valid_to>now()))
    if resource_id:statement=statement.where(Resource.id==resource_id)
    if person_id:statement=statement.where(Person.id==person_id)
    if role:statement=statement.where(ResourcePerson.role==role)
    if q:statement=statement.where(or_(Resource.name.ilike('%'+q+'%'),Person.display_name.ilike('%'+q+'%')))
    total=session.scalar(select(func.count()).select_from(statement.subquery()))
    rows=session.execute(statement.order_by(Resource.name,ResourcePerson.id).offset((page-1)*page_size).limit(page_size)).all()
    items=[ResourceRole(id=r.id,resource_id=resource.id,resource_name=resource.name,person_id=person.id,person_name=person.display_name,role=r.role,confirmation=r.confirmation,valid_from=r.valid_from.isoformat(),valid_to=r.valid_to.isoformat() if r.valid_to else None) for r,resource,person in rows]
    return SuccessEnvelope(data=ResourceRolePage(items=items,pagination=dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)),error=None,meta=ResponseMeta(request_id=request.state.request_id))
@router.get('/asset-graph',response_model=SuccessEnvelope[LocalGraph],operation_id='getLocalAssetGraph')
def graph(request:Request,object_id:UUID,kind:Literal['resource','company','platform','person','identity'],
          _:Annotated[PolicySubject,Depends(require_capability('resource.read'))],
          session:Annotated[Session,Depends(database_session)],depth:int=Query(default=1,ge=1,le=2)):
    return SuccessEnvelope(data=local_graph(session,kind,object_id,depth),error=None,meta=ResponseMeta(request_id=request.state.request_id))
