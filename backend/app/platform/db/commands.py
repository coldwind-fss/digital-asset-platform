"""Shared transaction mechanics; domain rules remain in their owning module."""
from datetime import UTC, datetime
from uuid import UUID
from fastapi import Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.platform.db.models import AuditEvent, Resource
from app.platform.http.errors import ApiException


def now():
    return datetime.now(UTC)


def actor(request: Request) -> UUID:
    principal = getattr(request.state,"policy_subject",None)
    if not principal or not principal.authenticated:
        raise ApiException(401,"AUTHENTICATION_REQUIRED","请先登录")
    return UUID(principal.subject_id)


def write_resource(session: Session, resource_id: UUID, expected_version: int | None = None):
    resource = session.scalar(select(Resource).where(Resource.id==resource_id).with_for_update().execution_options(populate_existing=True))
    if resource is None or resource.archived_at is not None:
        raise ApiException(404,"RESOURCE_NOT_FOUND","资源不存在或不可见")
    principal = session.info.get("local_principal")
    if principal and principal.role != "admin" and resource_id not in session.info["writable_resource_ids"]:
        raise ApiException(403,"PERMISSION_DENIED","当前对象仅允许查阅")
    if expected_version is not None and resource.version != expected_version:
        raise ApiException(409,"STATE_CONFLICT","资源版本已变化，请刷新后重试")
    return resource


def record_event(session: Session, event: str, actor_id: UUID, request_id: str | UUID, resource_id: UUID | None=None, data: dict | None=None):
    session.add(AuditEvent(actor_person_id=actor_id,actor_kind="person",event_type=event,resource_id=resource_id,request_id=UUID(str(request_id)),safe_after=data or {}))


def require_idempotency_key(idempotency_key: str = Header(alias="Idempotency-Key")) -> str:
    try:
        UUID(idempotency_key)
    except ValueError:
        raise ApiException(422,"INVALID_IDEMPOTENCY_KEY","幂等键必须是UUID") from None
    return idempotency_key
