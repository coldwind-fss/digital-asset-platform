from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, exists, func, select
from sqlalchemy.orm import Session

from app.modules.identity_access.public import PolicySubject, require_capability
from app.modules.resources.api.schemas import (
    AccountView,
    CompanyLinkView,
    MyResourcePage,
    MyResourceSummary,
    OrganizationSummary,
    Pagination,
    PersonAssignmentView,
    PersonSummary,
    ResourceCreateRequest,
    ResourcePage,
    ResourcePatchRequest,
    RelationPage,
    ResourceSummary,
    ResourceRelationCreateRequest,
    ResourceRelationView,
    ResourceView,
    VersionReasonRequest,
)
from app.modules.resources.application.service import (
    create_resource,
    current_roles,
    create_resource_relation,
    end_resource_relation,
    get_resource,
    list_resources,
    list_resource_relations,
    patch_resource,
)
from app.modules.resources.domain.rules import ResourceRuleError, validate_attributes
from app.platform.db.models import (
    Account,
    Company,
    Department,
    Person,
    Resource,
    ResourceCompany,
    ResourcePerson,
    ResourceRelation,
    SubscriptionBudget,
)
from app.platform.db.session import database_session
from app.platform.http.errors import ApiException
from app.platform.http.pagination import PageSize
from app.platform.http.schemas import ResponseMeta, SuccessEnvelope

router = APIRouter(tags=["resources"])
SessionDependency = Annotated[Session, Depends(database_session)]
ReadSubject = Annotated[PolicySubject, Depends(require_capability("resource.read"))]
WriteSubject = Annotated[PolicySubject, Depends(require_capability("resource.write"))]
def _summary(session: Session, resource: Resource) -> ResourceSummary:
    department = session.get(Department, resource.owning_department_id) if resource.owning_department_id else None
    owner_row = session.scalar(
        select(Person)
        .join(ResourcePerson, ResourcePerson.person_id == Person.id)
        .where(
            ResourcePerson.resource_id == resource.id,
            ResourcePerson.role == "owner",
            ResourcePerson.confirmation == "confirmed",
            ResourcePerson.valid_from <= datetime.now(UTC),
            or_(ResourcePerson.valid_to.is_(None), ResourcePerson.valid_to > datetime.now(UTC)),
        )
        .limit(1)
    )
    company_row = session.scalar(
        select(Company)
        .join(ResourceCompany, ResourceCompany.company_id == Company.id)
        .where(
            ResourceCompany.resource_id == resource.id,
            ResourceCompany.role == "owner",
            ResourceCompany.confirmation == "confirmed",
            ResourceCompany.valid_from <= datetime.now(UTC),
            or_(ResourceCompany.valid_to.is_(None), ResourceCompany.valid_to > datetime.now(UTC)),
        )
        .limit(1)
    )
    return ResourceSummary(
        id=resource.id,
        code=resource.code,
        name=resource.name,
        type_code=resource.type_code,
        provider_name=resource.provider_name,
        purpose=resource.purpose,
        owning_department=OrganizationSummary(id=department.id, display_name=department.name) if department else None,
        confirmed_company=OrganizationSummary(id=company_row.id, display_name=company_row.name) if company_row else None,
        owner=PersonSummary(id=owner_row.id, display_name=owner_row.display_name) if owner_row else None,
        lifecycle=resource.lifecycle,
        verification=resource.verification,
        version=resource.version,
        updated_at=resource.updated_at,
    )


def _view(session: Session, resource: Resource) -> ResourceView:
    from app.modules.subscriptions.public import resource_subscription_summary
    from app.modules.credentials.public import resource_credential_status
    ledger_summary=resource_subscription_summary(session,resource.id)
    summary = _summary(session, resource)
    people = []
    for assignment, person in session.execute(
        select(ResourcePerson, Person)
        .join(Person, Person.id == ResourcePerson.person_id)
        .where(ResourcePerson.resource_id == resource.id)
        .order_by(ResourcePerson.valid_from.desc())
    ).all():
        people.append(
            PersonAssignmentView(
                assignment_id=assignment.id,
                person=PersonSummary(id=person.id, display_name=person.display_name),
                role=assignment.role,
                confirmation=assignment.confirmation,
                valid_from=assignment.valid_from,
                valid_to=assignment.valid_to,
            )
        )
    company_links = []
    for link, company in session.execute(
        select(ResourceCompany, Company)
        .join(Company, Company.id == ResourceCompany.company_id)
        .where(ResourceCompany.resource_id == resource.id)
        .order_by(ResourceCompany.valid_from.desc())
    ).all():
        company_links.append(
            CompanyLinkView(
                assignment_id=link.id,
                company=OrganizationSummary(id=company.id, display_name=company.name),
                role=link.role,
                confirmation=link.confirmation,
                valid_from=link.valid_from,
                valid_to=link.valid_to,
            )
        )
    attributes = dict(resource.attributes or {})
    principal=session.info.get("local_principal")
    may_view_finance=principal is None or "finance.read" in principal.capabilities
    if not may_view_finance:
        for field in ("budgets","payment_label","settlement_mode"):
            attributes.pop(field,None)
    if resource.type_code == "service_subscription" and may_view_finance:
        attributes["budgets"] = [
            {
                "amount": f"{budget.amount:.2f}",
                "currency": budget.currency,
                "period": budget.period,
                "meaning": budget.meaning,
            }
            for budget in session.scalars(
                select(SubscriptionBudget).where(SubscriptionBudget.resource_id == resource.id).order_by(SubscriptionBudget.position)
            ).all()
        ]
    account = session.get(Account, resource.id)
    account_view = None
    if account:
        account_view = AccountView(
            identifier=account.identifier_masked,
            login_methods=account.login_methods,
            account_role=account.account_role,
            scope_label=account.scope_label,
        )
    missing_fields = []
    if summary.owner is None:
        missing_fields.append("owner")
    if resource.type_code in {"platform_account", "mailbox_account"} and account is None:
        missing_fields.append("account")
    return ResourceView(
        **summary.model_dump(),
        people=people,
        company_links=company_links,
        usage_mode=resource.usage_mode,
        visibility_scope=resource.visibility_scope,
        attributes=attributes,
        account=account_view,
        credential_status=resource_credential_status(session,resource.id),
        subscription_summary=ledger_summary,
        missing_fields=missing_fields,
        capabilities={"read": True, "edit": principal is None or ("resource.write" in principal.capabilities and (principal.role=="admin" or resource.id in session.info.get("writable_resource_ids",set())))},
        created_at=resource.created_at,
        platform_id=resource.platform_id,
    )


def _relation_view(
    session: Session,
    relation: ResourceRelation,
    source: Resource,
    target: Resource,
    direction: str,
) -> ResourceRelationView:
    return ResourceRelationView(
        id=relation.id,
        source=_summary(session, source),
        target=_summary(session, target),
        relation_type=relation.relation_type,
        direction=direction,
        confirmation=relation.confirmation,
        valid_from=relation.valid_from,
        valid_to=relation.valid_to,
        note=relation.note,
        version=relation.version,
    )


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(request_id=request.state.request_id)


@router.get("/resources", response_model=SuccessEnvelope[ResourcePage])
def list_resource_route(
    request: Request,
    _subject: ReadSubject,
    session: SessionDependency,
    q: str | None = Query(default=None, max_length=100),
    type_code: list[str] | None = Query(default=None),
    owner_id: UUID | None = None,
    department_id: UUID | None = None,
    company_id: UUID | None = None,
    provider_name: str | None = Query(default=None, max_length=200),
    lifecycle: str | None = None,
    verification: str | None = None,
    usage_mode: str | None = None,
    archived: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
    sort: str = Query(default="-updated_at,id", pattern=r"^-?(updated_at|name|id)(,-?(updated_at|name|id))*$"),
) -> SuccessEnvelope[ResourcePage]:
    rows, total = list_resources(
        session,
        page=page,
        page_size=page_size,
        sort=sort,
        q=q,
        type_code=type_code,
        owner_id=owner_id,
        department_id=department_id,
        company_id=company_id,
        provider_name=provider_name,
        lifecycle=lifecycle,
        verification=verification,
        usage_mode=usage_mode,
        archived=archived,
    )
    data = ResourcePage(
        items=[_summary(session, resource) for resource in rows],
        pagination=Pagination(page=page, page_size=page_size, total=total, has_next=page * page_size < total),
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.post("/resources", response_model=SuccessEnvelope[ResourceView], status_code=201)
def create_resource_route(
    request: Request,
    payload: ResourceCreateRequest,
    _subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ResourceView]:
    try:
        resource = create_resource(session, payload)
    except ResourceRuleError as error:
        raise ApiException(422, "VALIDATION_FAILED", str(error)) from None
    return SuccessEnvelope(data=_view(session, resource), error=None, meta=_meta(request))


@router.get("/resources/{resource_id}", response_model=SuccessEnvelope[ResourceView])
def get_resource_route(
    request: Request,
    resource_id: UUID,
    _subject: ReadSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ResourceView]:
    resource = get_resource(session, resource_id)
    return SuccessEnvelope(data=_view(session, resource), error=None, meta=_meta(request))


@router.patch("/resources/{resource_id}", response_model=SuccessEnvelope[ResourceView])
def patch_resource_route(
    request: Request,
    resource_id: UUID,
    payload: ResourcePatchRequest,
    _subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ResourceView]:
    resource = patch_resource(session, resource_id, payload)
    return SuccessEnvelope(data=_view(session, resource), error=None, meta=_meta(request))


@router.get("/me/resources", response_model=SuccessEnvelope[MyResourcePage])
def list_my_resources_route(
    request: Request,
    subject: ReadSubject,
    session: SessionDependency,
    role: list[str] | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[MyResourcePage]:
    if not subject.subject_id:
        raise ApiException(401, "AUTHENTICATION_REQUIRED", "请先登录")
    try:
        subject_id = UUID(subject.subject_id)
    except ValueError:
        raise ApiException(401, "AUTHENTICATION_REQUIRED", "当前测试主体 ID 无效") from None
    requested_roles = set(role or {"owner", "maintainer", "use", "controller"})
    requested_roles -= {"owner", "maintainer", "use", "controller"}
    if requested_roles:
        raise ApiException(422, "VALIDATION_FAILED", "role 参数不受支持")
    statement = select(Resource).where(
        Resource.archived_at.is_(None),
        exists(
            select(ResourcePerson.id).where(
                ResourcePerson.resource_id == Resource.id,
                ResourcePerson.person_id == subject_id,
                ResourcePerson.role.in_(role or ["owner", "maintainer", "use", "controller"]),
                ResourcePerson.confirmation == "confirmed",
                ResourcePerson.valid_from <= datetime.now(UTC),
            or_(ResourcePerson.valid_to.is_(None), ResourcePerson.valid_to > datetime.now(UTC)),
            )
        ),
    ).order_by(Resource.updated_at.desc(), Resource.id.asc())
    if q:
        needle='%'+q.strip()+'%'
        statement=statement.where(or_(Resource.name.ilike(needle),Resource.code.ilike(needle),Resource.provider_name.ilike(needle),Resource.purpose.ilike(needle)))
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    rows = list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all())
    data = MyResourcePage(
        items=[MyResourceSummary(**_summary(session, item).model_dump(), my_roles=current_roles(session, item.id, subject_id)) for item in rows],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=int(total or 0),
            has_next=page * page_size < int(total or 0),
        ),
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.get("/resources/{resource_id}/relations", response_model=SuccessEnvelope[RelationPage])
def list_resource_relations_route(
    request: Request,
    resource_id: UUID,
    _subject: ReadSubject,
    session: SessionDependency,
    direction: Literal["outgoing", "incoming", "both"] = Query(default="both"),
    relation_type: Literal["uses", "managed_by", "part_of"] | None = None,
    include_history: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[RelationPage]:
    rows, total = list_resource_relations(
        session,
        resource_id,
        direction=direction,
        relation_type=relation_type,
        include_history=include_history,
        page=page,
        page_size=page_size,
    )
    data = RelationPage(
        items=[_relation_view(session, *row) for row in rows],
        pagination=Pagination(page=page, page_size=page_size, total=total, has_next=page * page_size < total),
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.post("/resources/{resource_id}/relations", response_model=SuccessEnvelope[ResourceRelationView], status_code=201)
def create_resource_relation_route(
    request: Request,
    resource_id: UUID,
    payload: ResourceRelationCreateRequest,
    _subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ResourceRelationView]:
    relation = create_resource_relation(session, resource_id, payload)
    source = get_resource(session, relation.source_resource_id)
    target = get_resource(session, relation.target_resource_id)
    return SuccessEnvelope(
        data=_relation_view(session, relation, source, target, "outgoing"),
        error=None,
        meta=_meta(request),
    )


@router.post(
    "/resources/{resource_id}/relations/{relation_id}/actions/end",
    response_model=SuccessEnvelope[ResourceRelationView],
)
def end_resource_relation_route(
    request: Request,
    resource_id: UUID,
    relation_id: UUID,
    payload: VersionReasonRequest,
    _subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ResourceRelationView]:
    relation = end_resource_relation(session, resource_id, relation_id, payload)
    source = get_resource(session, relation.source_resource_id)
    target = get_resource(session, relation.target_resource_id)
    return SuccessEnvelope(
        data=_relation_view(session, relation, source, target, "outgoing"),
        error=None,
        meta=_meta(request),
    )
