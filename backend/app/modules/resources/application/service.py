from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Select, delete, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.modules.resources.api.schemas import (
    ResourceCreateRequest,
    ResourcePatchRequest,
    ResourceRelationCreateRequest,
    VersionReasonRequest,
)
from app.modules.resources.domain.rules import ResourceRuleError, validate_account_profile, validate_attributes
from app.platform.db.models import (
    Account,
    Company,
    Department,
    Material,
    Person,
    Resource,
    ResourceCompany,
    ResourcePerson,
    ResourceRelation,
    SubscriptionBudget,
    SubscriptionProfile,
    Platform, ProvenanceEntry,
)
from app.platform.http.errors import ApiException


def _safe_code() -> str:
    return f"RES-{uuid4().hex[:12].upper()}"


def _check_finance_write(session: Session, attributes: dict) -> None:
    principal=session.info.get("local_principal")
    if principal and "finance.write" not in principal.capabilities and set(attributes)&{"budgets","payment_label","settlement_mode"}:
        raise ApiException(403,"PERMISSION_DENIED","费用资料需要独立管理权限")


def _record_resource_event(session,resource,event,data=None):
    if session.info.get("actor_id") and session.info.get("request_id"):
        from app.platform.db.commands import record_event
        record_event(session,event,session.info["actor_id"],session.info["request_id"],resource.id,data or {"version":resource.version})


def validate_relation_endpoints(source_type: str,target_type: str,relation_type: str) -> None:
    accounts={"platform_account","mailbox_account"}
    if relation_type=="managed_by" and (source_type in accounts or target_type not in accounts):
        raise ApiException(422,"INVALID_RELATION_ENDPOINT","管理关系必须从服务资源指向实际账号")
    if relation_type=="contains" and (source_type!="business_space" or target_type in accounts):
        raise ApiException(422,"INVALID_RELATION_ENDPOINT","包含关系必须从业务空间指向服务资源")
    if relation_type=="part_of" and (target_type!="business_space" or source_type in accounts):
        raise ApiException(422,"INVALID_RELATION_ENDPOINT","所属空间关系必须指向业务空间")
    if relation_type in {"uses","depends_on"} and (source_type in accounts or target_type in accounts):
        raise ApiException(422,"INVALID_RELATION_ENDPOINT","依赖关系仅适用于实际服务资源")


def _rule_error(error: ResourceRuleError) -> ApiException:
    from app.platform.http.schemas import FieldError

    return ApiException(
        422,
        "VALIDATION_FAILED",
        "请检查填写内容",
        details=[FieldError(field=error.field, code="INVALID_VALUE", message=str(error))],
    )


def _reference_not_found(field: str) -> ApiException:
    from app.platform.http.schemas import FieldError

    return ApiException(
        404,
        "REFERENCE_NOT_FOUND",
        "关联对象不存在或不可见",
        details=[FieldError(field=field, code="NOT_FOUND", message="关联对象不存在或不可见")],
    )


def _protected_identifier_error() -> ApiException:
    return ApiException(
        503,
        "DEPENDENCY_UNAVAILABLE",
        "受保护标识存储尚未配置，当前只能保存不含标识的账号档案",
        retryable=True,
    )


def _ensure_department(session: Session, department_id: UUID | None) -> None:
    if department_id is not None and session.get(Department, department_id) is None:
        raise _reference_not_found("owning_department_id")


def _store_account(session: Session, resource: Resource, payload: dict[str, Any]) -> None:
    settings = session.info.get("settings")
    if (payload.get("identifier") or payload.get("aliases")) and (not settings or not settings.credential_master_key):
        raise _protected_identifier_error()
    methods = payload.get("login_methods") or ["unknown"]
    account = Account(
        resource_id=resource.id,
        login_methods=methods,
        account_role=payload.get("account_role") or "unknown",
        scope_label=payload.get("scope_label"),
    )
    session.add(account)
    if payload.get("identifier"):
        from app.modules.credentials.public import protect_identifier
        protected = protect_identifier(settings,payload["identifier"],f"account-identifier:{resource.id}")
        account.identifier_ciphertext,account.identifier_nonce,account.key_version=protected.ciphertext,protected.nonce,protected.key_version
        value=payload["identifier"]
        account.identifier_masked=value[:2]+"***"+(value[-2:] if len(value)>4 else "")
    if resource.type_code == "mailbox_account" and (payload.get("identifier") or payload.get("aliases")):
        from app.modules.bindings.public import create_mailbox_contacts
        create_mailbox_contacts(session,resource,payload)


def _store_subscription(session: Session, resource: Resource, attributes: dict[str, Any]) -> None:
    if resource.type_code != "service_subscription":
        return
    profile = SubscriptionProfile(
        resource_id=resource.id,
        plan=attributes.get("plan"),
        renewal_day=attributes.get("renewal_day"),
        expires_on=datetime.fromisoformat(attributes["expires_on"]).replace(tzinfo=UTC) if attributes.get("expires_on") else None,
        payment_label=attributes.get("payment_label"),
        settlement_mode=attributes.get("settlement_mode"),
    )
    session.add(profile)
    for position, budget in enumerate(attributes.get("budgets", [])):
        session.add(
            SubscriptionBudget(
                resource_id=resource.id,
                position=position,
                amount=Decimal(str(budget["amount"])),
                currency=budget["currency"],
                period=budget["period"],
                meaning=budget["meaning"],
            )
        )


def _ensure_people_and_companies(session: Session, payload: ResourceCreateRequest) -> None:
    for index, link in enumerate(payload.people):
        if session.get(Person, link.person_id) is None:
            raise _reference_not_found(f"people.{index}.person_id")
    for index, link in enumerate(payload.company_links):
        if session.get(Company, link.company_id) is None:
            raise _reference_not_found(f"company_links.{index}.company_id")
    for index, relation in enumerate(payload.relations):
        target = session.get(Resource, relation.target_id)
        if target is None or target.archived_at is not None:
            raise _reference_not_found(f"relations.{index}.target_id")
        validate_relation_endpoints(payload.type_code.value,target.type_code,relation.relation_type)
        if relation.relation_type == "managed_by" and session.get(Account, target.id) is None:
            raise ApiException(422, "VALIDATION_FAILED", f"relations.{index}.target_id 必须是账号资源")


def _store_materials_and_relations(session: Session, resource: Resource, payload: ResourceCreateRequest) -> None:
    for index, relation in enumerate(payload.relations):
        if relation.target_id == resource.id:
            raise ApiException(422, "VALIDATION_FAILED", f"relations.{index}.target_id 不能指向当前资源")
        if relation.relation_type in {"managed_by", "part_of"} and _management_path_exists(
            session, relation.target_id, resource.id
        ):
            raise ApiException(409, "STATE_CONFLICT", f"relations.{index} 会形成 managed_by/part_of 环路")
        session.add(
            ResourceRelation(
                source_resource_id=resource.id,
                target_resource_id=relation.target_id,
                relation_type=relation.relation_type,
                confirmation="proposed",
                note=relation.note,
            )
        )
    forbidden_terms = ("password", "api key", "secret", "token", "密码", "密钥")
    for index, material in enumerate(payload.materials):
        from app.modules.materials.public import validate_classification
        validate_classification(session,material.classification)
        if material.kind == "attachment":
            raise ApiException(
                422,
                "ATTACHMENT_REQUIRES_RESOURCE",
                "请先保存档案，再上传并关联该档案的私有附件",
            )
        if material.body and any(term in material.body.lower() for term in forbidden_terms):
            raise ApiException(422, "VALIDATION_FAILED", f"materials.{index}.body 不得包含凭据或秘密")
        session.add(
            Material(
                resource_id=resource.id,
                kind=material.kind,
                title=material.title or material.kind,
                url=material.url,
                body=material.body,
                file_ref=material.file_ref,
                classification=material.classification or "normal",
            )
        )


def create_resource(session: Session, payload: ResourceCreateRequest) -> Resource:
    account_payload = payload.account.model_dump(exclude_unset=True) if payload.account else None
    try:
        attributes = validate_attributes(payload.type_code.value, payload.attributes)
        validate_account_profile(payload.type_code.value, account_payload)
    except ResourceRuleError as error:
        raise _rule_error(error) from None
    _ensure_department(session, payload.owning_department_id)
    _ensure_people_and_companies(session, payload)
    if payload.platform_id is not None and session.get(Platform,payload.platform_id) is None:
        raise _reference_not_found("platform_id")
    _check_finance_write(session, attributes)

    resource = Resource(
        code=_safe_code(),
        name=payload.name,
        type_code=payload.type_code.value,
        provider_name=payload.provider_name,
        purpose=payload.purpose,
        owning_department_id=payload.owning_department_id,
        usage_mode=payload.usage_mode.value if payload.usage_mode else "normal",
        attributes=attributes,
        platform_id=payload.platform_id,
        lifecycle=payload.lifecycle,
    )
    session.add(resource)
    session.flush()
    principal=session.info.get("local_principal")
    session.add(ProvenanceEntry(resource_id=resource.id,source_kind="manual",label=payload.source_note,created_by_person_id=principal.person_id if principal else None))

    if resource.type_code in {"platform_account","mailbox_account"}:
        _store_account(session, resource, account_payload or {})
    _store_subscription(session, resource, attributes)
    for link in payload.people:
        session.add(
            ResourcePerson(
                resource_id=resource.id,
                person_id=link.person_id,
                role=link.role,
                confirmation="proposed",
            )
        )
    for link in payload.company_links:
        session.add(
            ResourceCompany(
                resource_id=resource.id,
                company_id=link.company_id,
                role=link.role,
                confirmation="proposed",
            )
        )
    _store_materials_and_relations(session, resource, payload)
    _record_resource_event(session,resource,"resource.created",{"type_code":resource.type_code,"version":1})
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiException(409, "STATE_CONFLICT", "资源登记与已有数据冲突") from None
    session.refresh(resource)
    return resource


def _resource_query_filters(
    statement: Select[tuple[Resource]],
    *,
    q: str | None,
    type_code: list[str] | None,
    owner_id: UUID | None,
    department_id: UUID | None,
    company_id: UUID | None,
    provider_name: str | None,
    lifecycle: str | None,
    verification: str | None,
    usage_mode: str | None,
    archived: bool,
) -> Select[tuple[Resource]]:
    conditions = [Resource.archived_at.is_not(None) if archived else Resource.archived_at.is_(None)]
    if q:
        needle = f"%{q.strip()}%"
        conditions.append(or_(Resource.name.ilike(needle), Resource.code.ilike(needle), Resource.provider_name.ilike(needle), Resource.purpose.ilike(needle)))
    if type_code:
        conditions.append(Resource.type_code.in_(type_code))
    if owner_id:
        conditions.append(
            exists(
                select(ResourcePerson.id).where(
                    ResourcePerson.resource_id == Resource.id,
                    ResourcePerson.person_id == owner_id,
                    ResourcePerson.role == "owner",
                    ResourcePerson.confirmation == "confirmed",
                    ResourcePerson.valid_from <= datetime.now(UTC),
            or_(ResourcePerson.valid_to.is_(None), ResourcePerson.valid_to > datetime.now(UTC)),
                )
            )
        )
    if department_id:
        conditions.append(Resource.owning_department_id == department_id)
    if company_id:
        conditions.append(
            exists(
                select(ResourceCompany.id).where(
                    ResourceCompany.resource_id == Resource.id,
                    ResourceCompany.company_id == company_id,
                    ResourceCompany.confirmation == "confirmed",
                    ResourceCompany.valid_from <= datetime.now(UTC),
            or_(ResourceCompany.valid_to.is_(None), ResourceCompany.valid_to > datetime.now(UTC)),
                )
            )
        )
    if provider_name:
        conditions.append(Resource.provider_name.ilike(f"%{provider_name.strip()}%"))
    if lifecycle:
        conditions.append(Resource.lifecycle == lifecycle)
    if verification:
        conditions.append(Resource.verification == verification)
    if usage_mode:
        conditions.append(Resource.usage_mode == usage_mode)
    return statement.where(*conditions)


def list_resources(
    session: Session,
    *,
    page: int,
    page_size: int,
    sort: str,
    q: str | None = None,
    type_code: list[str] | None = None,
    owner_id: UUID | None = None,
    department_id: UUID | None = None,
    company_id: UUID | None = None,
    provider_name: str | None = None,
    lifecycle: str | None = None,
    verification: str | None = None,
    usage_mode: str | None = None,
    archived: bool = False,
) -> tuple[list[Resource], int]:
    base = _resource_query_filters(
        select(Resource),
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
    sort_fields = {"updated_at": Resource.updated_at, "name": Resource.name, "id": Resource.id}
    for item in sort.split(","):
        descending = item.startswith("-")
        field = item[1:] if descending else item
        base = base.order_by(sort_fields[field].desc() if descending else sort_fields[field].asc())
    total_statement = _resource_query_filters(
        select(func.count()).select_from(Resource),
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
    total = int(session.scalar(total_statement) or 0)
    rows = list(session.scalars(base.offset((page - 1) * page_size).limit(page_size)).all())
    return rows, total


def get_resource(session: Session, resource_id: UUID, *, for_update: bool=False) -> Resource:
    resource = session.scalar(select(Resource).where(Resource.id==resource_id).with_for_update().execution_options(populate_existing=True)) if for_update else session.get(Resource, resource_id)
    if resource is None or resource.archived_at is not None:
        raise ApiException(404, "RESOURCE_NOT_FOUND", "资源不存在或不可见")
    return resource


def _replace_budgets(session: Session, resource_id: UUID, attributes: dict[str, Any]) -> None:
    if "budgets" not in attributes:
        return
    profile = session.get(SubscriptionProfile, resource_id)
    if profile is None:
        profile = SubscriptionProfile(resource_id=resource_id)
        session.add(profile)
    session.execute(delete(SubscriptionBudget).where(SubscriptionBudget.resource_id == resource_id))
    for position, budget in enumerate(attributes["budgets"]):
        session.add(
            SubscriptionBudget(
                resource_id=resource_id,
                position=position,
                amount=Decimal(str(budget["amount"])),
                currency=budget["currency"],
                period=budget["period"],
                meaning=budget["meaning"],
            )
        )


def patch_resource(session: Session, resource_id: UUID, payload: ResourcePatchRequest) -> Resource:
    resource = get_resource(session, resource_id, for_update=True)
    if resource.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "资源已被其他操作更新，请刷新后重试")
    changes = payload.changes
    if "attributes" in changes.model_fields_set and changes.attributes is not None:
        from app.platform.db.models import SubscriptionLedger
        ledger_table=SubscriptionLedger.__table__
        if session.connection().execute(select(ledger_table.c.id).where(ledger_table.c.resource_id==resource.id)).first():
            protected={'plan','seats','billing_cycle','expires_on','renewal_day','budgets'}
            if any(changes.attributes.get(k)!=resource.attributes.get(k) for k in protected):raise ApiException(409,'LEDGER_OWNS_FACTS','已建立账本的订阅资料需通过订阅接口维护')
        _check_finance_write(session, changes.attributes)
        try:
            validate_attributes(resource.type_code, changes.attributes)
        except ResourceRuleError as error:
            raise _rule_error(error) from None
        preserved={}
        principal=session.info.get("local_principal")
        if principal and "finance.write" not in principal.capabilities:
            preserved={k:v for k,v in (resource.attributes or {}).items() if k in {"budgets","payment_label","settlement_mode"}}
        resource.attributes = {**changes.attributes,**preserved}
        _replace_budgets(session, resource.id, changes.attributes)
    for field in ("name", "provider_name", "purpose"):
        if field in changes.model_fields_set:
            setattr(resource, field, getattr(changes, field))
    if "usage_mode" in changes.model_fields_set:
        if changes.usage_mode is None:
            raise ApiException(422, "VALIDATION_FAILED", "usage_mode 不能清空")
        resource.usage_mode = changes.usage_mode.value
    if changes.account is not None:
        if resource.type_code not in {"platform_account", "mailbox_account"}:
            raise ApiException(422, "VALIDATION_FAILED", "当前资源类型不支持账号字段")
        account = session.get(Account, resource.id)
        if account is None:
            account = Account(resource_id=resource.id, login_methods=["unknown"], account_role="unknown")
            session.add(account)
        if "login_methods" in changes.account.model_fields_set:
            account.login_methods = changes.account.login_methods or ["unknown"]
        if "account_role" in changes.account.model_fields_set:
            account.account_role = changes.account.account_role or "unknown"
        if "scope_label" in changes.account.model_fields_set:
            account.scope_label = changes.account.scope_label
    resource.version += 1
    resource.updated_at = datetime.now(UTC)
    _record_resource_event(session,resource,"resource.updated",{"version":resource.version,"fields":sorted(changes.model_fields_set)})
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiException(409, "STATE_CONFLICT", "资源更新与已有数据冲突") from None
    session.refresh(resource)
    return resource


def current_roles(session: Session, resource_id: UUID, subject_id: UUID) -> list[str]:
    rows = session.scalars(
        select(ResourcePerson.role).where(
            ResourcePerson.resource_id == resource_id,
            ResourcePerson.person_id == subject_id,
            ResourcePerson.confirmation == "confirmed",
            ResourcePerson.valid_from <= datetime.now(UTC),
            or_(ResourcePerson.valid_to.is_(None), ResourcePerson.valid_to > datetime.now(UTC)),
        )
    ).all()
    return sorted(set(rows))


def current_owner_assignment(session: Session, resource_id: UUID) -> ResourcePerson | None:
    return session.scalar(
        select(ResourcePerson)
        .where(
            ResourcePerson.resource_id == resource_id,
            ResourcePerson.role == "owner",
            ResourcePerson.confirmation == "confirmed",
            ResourcePerson.valid_from <= datetime.now(UTC),
            or_(ResourcePerson.valid_to.is_(None), ResourcePerson.valid_to > datetime.now(UTC)),
        )
        .limit(1)
    )


def apply_owner_transfer(
    session: Session,
    resource_id: UUID,
    *,
    expected_resource_version: int,
    expected_assignment_id: UUID | None,
    to_person_id: UUID,
) -> tuple[Resource, ResourcePerson | None, ResourcePerson]:
    resource = get_resource(session, resource_id)
    if resource.version != expected_resource_version:
        raise ApiException(409, "STATE_CONFLICT", "资源已被其他操作更新，请刷新后重试")
    target_person = session.get(Person, to_person_id)
    if target_person is None or target_person.status != "active":
        raise ApiException(422, "VALIDATION_FAILED", "目标负责人不存在或当前不可用")
    current_owner = current_owner_assignment(session, resource_id)
    if expected_assignment_id is not None and (
        current_owner is None or current_owner.id != expected_assignment_id
    ):
        raise ApiException(409, "STATE_CONFLICT", "当前负责人事实已变化，请刷新后重试")
    now = datetime.now(UTC)
    if current_owner is not None:
        current_owner.valid_to = now
        current_owner.version += 1
        session.flush()
    replacement = ResourcePerson(
        resource_id=resource.id,
        person_id=target_person.id,
        role="owner",
        confirmation="confirmed",
        valid_from=now,
    )
    session.add(replacement)
    resource.version += 1
    resource.updated_at = now
    session.flush()
    return resource, current_owner, replacement


def _management_path_exists(session: Session, start_id: UUID, target_id: UUID) -> bool:
    """Return whether management/containment edges already reach target_id."""
    edges: dict[UUID, set[UUID]] = {}
    for source_id, destination_id in session.execute(
        select(ResourceRelation.source_resource_id, ResourceRelation.target_resource_id).where(
            ResourceRelation.relation_type.in_(["managed_by", "part_of"]),
            ResourceRelation.confirmation != "rejected",
            ResourceRelation.valid_to.is_(None),
        )
    ).all():
        edges.setdefault(source_id, set()).add(destination_id)

    pending = [start_id]
    visited: set[UUID] = set()
    while pending:
        current = pending.pop()
        if current == target_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(edges.get(current, set()) - visited)
    return False


def _check_containment_cycle(session,source_id,target_id,kind):
    if kind not in {"contains","part_of"}:return
    from sqlalchemy import text
    session.execute(text("SELECT pg_advisory_xact_lock(731004211)"))
    edges={}
    for a,b,k in session.connection().execute(select(ResourceRelation.source_resource_id,ResourceRelation.target_resource_id,ResourceRelation.relation_type).where(ResourceRelation.relation_type.in_(["contains","part_of"]),ResourceRelation.confirmation!="rejected",ResourceRelation.valid_to.is_(None))):
        if k=="part_of":a,b=b,a
        edges.setdefault(a,set()).add(b)
    if kind=="part_of":source_id,target_id=target_id,source_id
    if target_id in edges.get(source_id,set()):
        raise ApiException(409,"DUPLICATE_RELATION","同一包含事实已存在，不另建反向副本")
    todo=[target_id];visited=set()
    while todo:
        node=todo.pop()
        if node==source_id:raise ApiException(409,"CONTAINMENT_CYCLE","包含关系不能形成环路")
        if node in visited:continue
        visited.add(node);todo.extend(edges.get(node,set())-visited)


def create_resource_relation(
    session: Session,
    resource_id: UUID,
    payload: ResourceRelationCreateRequest,
) -> ResourceRelation:
    from sqlalchemy import text
    session.execute(text("SELECT pg_advisory_xact_lock(731004211)"))
    source = get_resource(session, resource_id,for_update=True)
    if source.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "资源已被其他操作更新，请刷新后重试")
    target = get_resource(session, payload.target_id)
    if source.id == target.id:
        raise ApiException(422, "VALIDATION_FAILED", "资源不能与自身建立关系")
    validate_relation_endpoints(source.type_code,target.type_code,payload.relation_type)
    _check_containment_cycle(session,source.id,target.id,payload.relation_type)
    from app.modules.resources.application.facts import supersede_declaration
    supersede_declaration(session,resource_id,payload.relation_type,payload.note)
    if payload.relation_type == "managed_by" and session.get(Account, target.id) is None:
        raise ApiException(422, "VALIDATION_FAILED", "managed_by 的目标必须是账号资源")
    if payload.relation_type in {"managed_by", "part_of"} and _management_path_exists(session, target.id, source.id):
        raise ApiException(409, "STATE_CONFLICT", "managed_by/part_of 关系不能形成环路")
    duplicate = session.scalar(
        select(ResourceRelation.id).where(
            ResourceRelation.source_resource_id == source.id,
            ResourceRelation.target_resource_id == target.id,
            ResourceRelation.relation_type == payload.relation_type,
            ResourceRelation.confirmation != "rejected",
            ResourceRelation.valid_to.is_(None),
        )
    )
    if duplicate is not None:
        raise ApiException(409, "STATE_CONFLICT", "当前关系已经存在")
    relation = ResourceRelation(
        source_resource_id=source.id,
        target_resource_id=target.id,
        relation_type=payload.relation_type,
        confirmation="proposed",
        note=payload.note,
    )
    session.add(relation)
    source.version += 1
    source.updated_at = datetime.now(UTC)
    _record_resource_event(session,source,"relation.created",{"relation_type":payload.relation_type})
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiException(409, "STATE_CONFLICT", "关系与已有数据冲突") from None
    session.refresh(relation)
    return relation


def list_resource_relations(
    session: Session,
    resource_id: UUID,
    *,
    direction: str,
    relation_type: str | None,
    include_history: bool,
    page: int,
    page_size: int,
) -> tuple[list[tuple[ResourceRelation, Resource, Resource, str]], int]:
    get_resource(session, resource_id)
    conditions = [ResourceRelation.confirmation != "rejected"]
    if not include_history:
        conditions.append(ResourceRelation.valid_to.is_(None))
    if relation_type:
        conditions.append(ResourceRelation.relation_type == relation_type)
    if direction == "outgoing":
        conditions.append(ResourceRelation.source_resource_id == resource_id)
    elif direction == "incoming":
        conditions.append(ResourceRelation.target_resource_id == resource_id)
    else:
        conditions.append(
            or_(ResourceRelation.source_resource_id == resource_id, ResourceRelation.target_resource_id == resource_id)
        )
    source_resource = aliased(Resource)
    target_resource = aliased(Resource)
    statement = (
        select(ResourceRelation)
        .join(source_resource, source_resource.id == ResourceRelation.source_resource_id)
        .join(target_resource, target_resource.id == ResourceRelation.target_resource_id)
        .where(
            *conditions,
            source_resource.archived_at.is_(None),
            target_resource.archived_at.is_(None),
        )
        .order_by(ResourceRelation.valid_from.desc(), ResourceRelation.id)
    )
    total = int(session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    relations = list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all())
    result: list[tuple[ResourceRelation, Resource, Resource, str]] = []
    for relation in relations:
        source = session.get(Resource, relation.source_resource_id)
        target = session.get(Resource, relation.target_resource_id)
        if source is None or target is None:
            continue
        result.append(
            (
                relation,
                source,
                target,
                "outgoing" if relation.source_resource_id == resource_id else "incoming",
            )
        )
    return result, total


def end_resource_relation(
    session: Session,
    resource_id: UUID,
    relation_id: UUID,
    payload: VersionReasonRequest,
) -> ResourceRelation:
    source = get_resource(session, resource_id,for_update=True)
    relation = session.get(ResourceRelation, relation_id)
    if relation is None or relation.source_resource_id != source.id or relation.valid_to is not None:
        raise ApiException(404, "RESOURCE_NOT_FOUND", "关系不存在或不可见")
    if relation.confirmation=="confirmed" or relation.relation_type in {"managed_by", "part_of", "contains"}:
        raise ApiException(403, "PERMISSION_DENIED", "管理/归属关系的结束必须通过治理事项")
    if source.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "资源已被其他操作更新，请刷新后重试")
    relation.valid_to = datetime.now(UTC)
    relation.version += 1
    source.version += 1
    source.updated_at = datetime.now(UTC)
    _record_resource_event(session,source,"relation.ended",{"relation_id":str(relation.id),"reason":payload.reason})
    session.commit()
    session.refresh(relation)
    return relation
