from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.governance.api.schemas import (
    ChangeCaseCreate,
    ChangeCasePatch,
    ChangeItemCreate,
    ChangeItemPatch,
    ChangeItemProposal,
    ChangeOwnerProposal,
    ConfirmChangeRequest,
    ExpectedVersionRequest,
    RecordExecutionRequest,
    VersionReasonRequest,
)
from app.modules.resources.public import apply_owner_transfer, current_owner_assignment, get_resource
from app.platform.db.models import AuditEvent, ChangeCase, ChangeItem, Material, Person, ResourcePerson
from app.platform.http.errors import ApiException


def _now() -> datetime:
    return datetime.now(UTC)


def _person(session: Session, person_id: UUID, *, active: bool = False) -> Person:
    person = session.get(Person, person_id)
    if person is None or (active and person.status != "active"):
        raise ApiException(422, "VALIDATION_FAILED", "人员不存在或当前不可用")
    return person


def _case(session: Session, case_id: UUID) -> ChangeCase:
    case = session.scalar(select(ChangeCase).where(ChangeCase.id == case_id).with_for_update())
    if case is None:
        raise ApiException(404, "RESOURCE_NOT_FOUND", "变更事项不存在或不可见")
    return case


def _item(session: Session, item_id: UUID) -> ChangeItem:
    item = session.get(ChangeItem, item_id)
    if item is None:
        raise ApiException(404, "RESOURCE_NOT_FOUND", "变更事项不存在或不可见")
    return item


def _audit(
    session: Session,
    *,
    resource_id: UUID | None,
    change_item_id: UUID | None,
    actor_id: UUID | None,
    request_id: UUID,
    event_type: str,
    safe_before: dict[str, object] | None = None,
    safe_after: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            resource_id=resource_id,
            change_item_id=change_item_id,
            actor_person_id=actor_id,
            actor_kind="person" if actor_id else "system",
            event_type=event_type,
            request_id=request_id,
            safe_before=safe_before,
            safe_after=safe_after,
        )
    )






def create_change_case(
    session: Session,
    payload: ChangeCaseCreate,
    *,
    actor_id: UUID,
    request_id: UUID,
) -> ChangeCase:
    _person(session, payload.coordinator_person_id,active=True)
    if payload.subject_person_id is not None:
        _person(session, payload.subject_person_id)
    case = ChangeCase(
        case_type=payload.case_type,
        subject_person_id=payload.subject_person_id,
        coordinator_person_id=payload.coordinator_person_id,
        reason=payload.reason,
        status="draft",
    )
    session.add(case)
    session.flush()
    _audit(
        session,
        resource_id=None,
        change_item_id=None,
        actor_id=actor_id,
        request_id=request_id,
        event_type="change_case_created",
        safe_after={"change_case_id": str(case.id), "case_type": case.case_type, "status": case.status},
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiException(409, "STATE_CONFLICT", "变更事项创建与已有数据冲突") from None
    session.refresh(case)
    return case


def list_change_cases(
    session: Session,
    *,
    subject_id: UUID,
    status: str | None,
    assigned_to_me: bool | None,
    awaiting_my_confirmation: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[ChangeCase], int]:
    statement = select(ChangeCase).order_by(ChangeCase.updated_at.desc(), ChangeCase.id)
    if status:
        statement = statement.where(ChangeCase.status == status)
    if assigned_to_me:
        statement = statement.where(ChangeCase.coordinator_person_id == subject_id)
    if awaiting_my_confirmation:
        statement = statement.where(
            ChangeCase.coordinator_person_id == subject_id,
            select(ChangeItem.id)
            .where(ChangeItem.case_id == ChangeCase.id, ChangeItem.status == "awaiting_confirmation")
            .exists(),
        )
    total = int(session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    return list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()), total


def get_change_case(session: Session, case_id: UUID) -> ChangeCase:
    return _case(session, case_id)


def patch_change_case(
    session: Session,
    case_id: UUID,
    payload: ChangeCasePatch,
    *,
    actor_id: UUID,
    request_id: UUID,
) -> ChangeCase:
    case = _case(session, case_id)
    if case.status != "draft":
        raise ApiException(409, "STATE_CONFLICT", "只有草稿变更事项可以修订")
    if case.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "变更事项已被其他操作更新，请刷新后重试")
    if "reason" in payload.model_fields_set:
        case.reason = payload.reason
    if "coordinator_person_id" in payload.model_fields_set:
        if payload.coordinator_person_id is None:
            raise ApiException(422, "VALIDATION_FAILED", "协调人不能清空")
        _person(session, payload.coordinator_person_id,active=True)
        case.coordinator_person_id = payload.coordinator_person_id
    if "subject_person_id" in payload.model_fields_set:
        if payload.subject_person_id is not None:
            _person(session, payload.subject_person_id)
        case.subject_person_id = payload.subject_person_id
    case.version += 1
    case.updated_at = _now()
    _audit(
        session,
        resource_id=None,
        change_item_id=None,
        actor_id=actor_id,
        request_id=request_id,
        event_type="change_case_updated",
        safe_after={"change_case_id": str(case.id), "version": case.version},
    )
    session.commit()
    session.refresh(case)
    return case


def list_change_items(
    session: Session,
    case_id: UUID,
    *,
    page: int,
    page_size: int,
) -> tuple[list[ChangeItem], int]:
    _case(session, case_id)
    statement = select(ChangeItem).where(ChangeItem.case_id == case_id).order_by(ChangeItem.created_at, ChangeItem.id)
    total = int(session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    return list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()), total




def get_change_item(session: Session, item_id: UUID) -> ChangeItem:
    return _item(session, item_id)


def submit_change_case(session: Session, case_id: UUID, payload: ExpectedVersionRequest, *, actor_id: UUID, request_id: UUID) -> ChangeCase:
    case = _case(session, case_id)
    if case.status != "draft" or case.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "变更事项状态或版本已变化，请刷新后重试")
    if session.scalar(select(ChangeItem.id).where(ChangeItem.case_id == case.id)) is None:
        raise ApiException(422, "VALIDATION_FAILED", "变更事项至少需要一个类型化事项")
    case.status = "active"
    case.version += 1
    case.updated_at = _now()
    _audit(session, resource_id=None, change_item_id=None, actor_id=actor_id, request_id=request_id, event_type="change_case_submitted", safe_after={"status": case.status, "version": case.version})
    session.commit()
    session.refresh(case)
    return case










def close_change_case(session: Session, case_id: UUID, payload: ExpectedVersionRequest, *, actor_id: UUID, request_id: UUID) -> ChangeCase:
    case = _case(session, case_id)
    if case.status in {"completed", "completed_with_exceptions", "cancelled"}:
        return case
    if case.status != "active" or case.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "变更事项状态或版本已变化，请刷新后重试")
    items = list(session.scalars(select(ChangeItem).where(ChangeItem.case_id == case.id)).all())
    if not items or any(item.status not in {"completed", "cancelled"} for item in items):
        raise ApiException(409, "STATE_CONFLICT", "仍有未完成的变更事项")
    if any(item.status == "cancelled" for item in items) and not payload.closure_note:
        raise ApiException(422,"VALIDATION_FAILED","有取消事项时必须说明关闭例外")
    case.status = "completed" if all(item.status == "completed" for item in items) else "cancelled" if all(item.status == "cancelled" for item in items) else "completed_with_exceptions"
    case.closed_at = _now()
    case.version += 1
    case.updated_at = _now()
    _audit(session, resource_id=None, change_item_id=None, actor_id=actor_id, request_id=request_id, event_type="change_case_closed", safe_after={"status": case.status, "version": case.version,"closure_note":payload.closure_note})
    session.commit()
    session.refresh(case)
    return case

# Stage 2 ports supersede the V2 owner-only execution path.
from app.modules.governance.application.stage2 import (create_change_item, patch_change_item, proposal_for_item, start_change_item, record_execution, confirm_change_item, cancel_change_item, confirm_cancellation, return_for_rework)
