from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.materials.api.schemas import MaterialCreateRequest, MaterialPatchRequest
from app.modules.resources.public import get_resource
from app.platform.db.models import AuditEvent, Material
from app.platform.http.errors import ApiException


_FORBIDDEN_TERMS = ("password", "api key", "secret", "token", "密码", "密钥")


def _safe_body(body: str | None) -> None:
    if body and any(term in body.lower() for term in _FORBIDDEN_TERMS):
        raise ApiException(422, "VALIDATION_FAILED", "资料正文不得包含凭据或秘密")


def validate_classification(session,classification):
    principal=session.info.get('local_principal')
    if classification not in {None,'normal'} and principal and 'materials.restricted' not in principal.capabilities:
        raise ApiException(403,'PERMISSION_DENIED','受限资料需要独立管理权限')


def _audit(session: Session, *, resource_id: UUID, actor_id: UUID, request_id: UUID, event_type: str, material_id: UUID) -> None:
    session.add(
        AuditEvent(
            resource_id=resource_id,
            actor_person_id=actor_id,
            actor_kind="person",
            event_type=event_type,
            request_id=request_id,
            safe_after={"material_id": str(material_id), "event_type": event_type},
        )
    )


def list_materials(session: Session, resource_id: UUID, *, page: int, page_size: int) -> tuple[list[Material], int]:
    get_resource(session, resource_id)
    statement = (
        select(Material)
        .where(Material.resource_id == resource_id, Material.archived_at.is_(None))
        .order_by(Material.updated_at.desc(), Material.id)
    )
    total = int(session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    return list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()), total


def create_material(
    session: Session,
    resource_id: UUID,
    payload: MaterialCreateRequest,
    *,
    actor_id: UUID,
    request_id: UUID,
) -> Material:
    from app.platform.db.commands import write_resource
    resource = write_resource(session, resource_id)
    validate_classification(session,payload.classification)
    if payload.kind == "attachment":
        from app.modules.materials.application.files import available_file
        try:file=available_file(session,UUID(payload.file_ref),resource_id)
        except ValueError:raise ApiException(422,'VALIDATION_FAILED','附件引用必须是文件UUID') from None
        if file.classification!='normal' and payload.classification in {None,'normal'}:raise ApiException(422,'VALIDATION_FAILED','资料不能降低附件的保密级别')
    _safe_body(payload.body)
    material = Material(
        resource_id=resource.id,
        kind=payload.kind,
        title=payload.title or payload.kind,
        url=payload.url,
        body=payload.body,
        file_ref=payload.file_ref,
        classification=payload.classification or "normal",
    )
    session.add(material)
    resource.version += 1
    resource.updated_at = datetime.now(UTC)
    session.flush()
    _audit(session, resource_id=resource.id, actor_id=actor_id, request_id=request_id, event_type="material_created", material_id=material.id)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiException(409, "STATE_CONFLICT", "资料保存与已有数据冲突") from None
    session.refresh(material)
    return material


def patch_material(
    session: Session,
    resource_id: UUID,
    material_id: UUID,
    payload: MaterialPatchRequest,
    *,
    actor_id: UUID,
    request_id: UUID,
) -> Material:
    from app.platform.db.commands import write_resource
    write_resource(session, resource_id)
    material = session.get(Material, material_id)
    if material is None or material.resource_id != resource_id or material.archived_at is not None:
        raise ApiException(404, "RESOURCE_NOT_FOUND", "资料不存在或不可见")
    if material.kind != payload.kind or material.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "资料类型或版本已变化，请刷新后重试")
    if material.kind == "attachment":
        from app.modules.materials.application.files import available_file
        file=available_file(session,UUID(material.file_ref),resource_id)
        if file.classification!='normal' and payload.changes.classification=='normal':raise ApiException(422,'VALIDATION_FAILED','资料不能降低附件的保密级别')
    changes = payload.changes
    if 'classification' in changes.model_fields_set:validate_classification(session,changes.classification)
    if "body" in changes.model_fields_set:
        _safe_body(changes.body)
        material.body = changes.body
    if "url" in changes.model_fields_set:
        material.url = changes.url
    if "title" in changes.model_fields_set:
        material.title = changes.title
    if "classification" in changes.model_fields_set:
        material.classification = changes.classification or "normal"
    material.version += 1
    material.updated_at = datetime.now(UTC)
    _audit(session, resource_id=resource_id, actor_id=actor_id, request_id=request_id, event_type="material_updated", material_id=material.id)
    session.commit()
    session.refresh(material)
    return material
