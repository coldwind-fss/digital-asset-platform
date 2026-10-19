from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.modules.credentials.api.schemas import CredentialAttachRequest, CredentialGrantCreate, CredentialRevealRequest, SecretStageCreate
from app.modules.credentials.application.crypto import (
    decrypt_secret,
    encrypt_secret,
    hash_stage_token,
    new_stage_token,
)
from app.modules.resources.public import get_resource
from app.platform.db.models import AuditEvent, CredentialGrant, CredentialRef, CredentialStage, Person
from app.platform.http.errors import ApiException


def _now() -> datetime:
    return datetime.now(UTC)


def _audit(
    session: Session,
    *,
    resource_id: UUID | None,
    actor_id: UUID | None,
    request_id: UUID,
    event_type: str,
    safe_after: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            resource_id=resource_id,
            actor_person_id=actor_id,
            actor_kind="person" if actor_id else "system",
            event_type=event_type,
            request_id=request_id,
            safe_after=safe_after,
        )
    )


def create_secret_stage(
    session: Session,
    settings: Settings,
    payload: SecretStageCreate,
) -> tuple[CredentialStage, str]:
    # The UUID participates in AES-GCM associated data, so it must exist before
    # encryption rather than waiting for SQLAlchemy's flush-time default.
    if payload.resource_id:
        from app.platform.db.commands import write_resource
        write_resource(session,payload.resource_id)
    stage = CredentialStage(id=uuid4(), kind=payload.kind,resource_id=payload.resource_id,purpose=payload.purpose)
    token = new_stage_token()
    encrypted = encrypt_secret(settings, payload.secret_value, associated_data=f"credential-stage:{stage.id}".encode())
    stage.token_hash = hash_stage_token(token)
    stage.ciphertext = encrypted.ciphertext
    stage.nonce = encrypted.nonce
    stage.key_version = encrypted.key_version
    stage.expires_at = _now() + timedelta(minutes=5)
    session.add(stage)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiException(409, "STATE_CONFLICT", "凭据暂存创建冲突，请重试") from None
    session.refresh(stage)
    return stage, token


def attach_credential(
    session: Session,
    settings: Settings,
    resource_id: UUID,
    payload: CredentialAttachRequest,
    *,
    actor_id: UUID,
    request_id: UUID,
) -> UUID:
    from app.platform.db.commands import write_resource
    resource = write_resource(session, resource_id,payload.expected_version)
    if resource.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "资源已被其他操作更新，请刷新后重试")
    stage = session.scalar(select(CredentialStage).where(CredentialStage.token_hash == hash_stage_token(payload.stage_token)).with_for_update().execution_options(populate_existing=True))
    now = _now()
    if stage is None or stage.consumed_at is not None or stage.expires_at <= now:
        raise ApiException(410, "STAGE_EXPIRED", "凭据暂存已过期或已使用，请重新输入")
    if stage.resource_id is not None and stage.resource_id!=resource_id:
        raise ApiException(410,"STAGE_TARGET_MISMATCH","凭据暂存不属于当前资源")
    if stage.purpose!="attach":raise ApiException(422,"STAGE_PURPOSE_MISMATCH","该暂存仅用于已准备的替换操作")
    if session.scalar(select(CredentialRef.id).where(CredentialRef.resource_id==resource_id,CredentialRef.kind==payload.kind,CredentialRef.status=="saved")):
        raise ApiException(409,"GOVERNANCE_REQUIRED","该类凭据已保存，替换请通过治理确认")
    if stage.kind != payload.kind:
        raise ApiException(422, "VALIDATION_FAILED", "凭据类别与暂存内容不一致")
    staged_plaintext = decrypt_secret(
        settings,
        ciphertext=stage.ciphertext,
        nonce=stage.nonce,
        key_version=stage.key_version,
        associated_data=f"credential-stage:{stage.id}".encode(),
    )
    # Bind the ciphertext to the stable credential ID before the insert flush.
    credential = CredentialRef(id=uuid4(), resource_id=resource.id, kind=stage.kind, status="saved")
    encrypted = encrypt_secret(settings, staged_plaintext, associated_data=f"credential:{credential.id}".encode())
    credential.ciphertext = encrypted.ciphertext
    credential.nonce = encrypted.nonce
    credential.key_version = encrypted.key_version
    session.add(credential)
    stage.consumed_at = now
    resource.version += 1
    resource.updated_at = now
    session.flush()
    _audit(
        session,
        resource_id=resource.id,
        actor_id=actor_id,
        request_id=request_id,
        event_type="credential_attached",
        safe_after={"credential_id": str(credential.id), "credential_status": credential.status, "key_version": credential.key_version},
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiException(409, "STATE_CONFLICT", "资源凭据更新冲突，请刷新后重试") from None
    return credential.id


def create_credential_grant(
    session: Session,
    credential_id: UUID,
    payload: CredentialGrantCreate,
    *,
    actor_id: UUID,
    request_id: UUID,
) -> CredentialGrant:
    credential = session.get(CredentialRef,credential_id)
    if credential is None:
        raise ApiException(404, "RESOURCE_NOT_FOUND", "凭据不存在或不可见")
    from app.platform.db.commands import write_resource
    write_resource(session,credential.resource_id)
    credential=session.scalar(select(CredentialRef).where(CredentialRef.id==credential_id).with_for_update().execution_options(populate_existing=True))
    if credential.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "凭据授权版本已变化，请刷新后重试")
    if credential.status!='saved':raise ApiException(409,'STATE_CONFLICT','仅有效凭据可以授权')
    if session.scalar(select(CredentialGrant.id).where(CredentialGrant.credential_id==credential_id,CredentialGrant.person_id==payload.person_id,CredentialGrant.capability==payload.capability,((CredentialGrant.valid_to.is_(None))|(CredentialGrant.valid_to>_now())))):
        raise ApiException(409,'STATE_CONFLICT','该人员已有相同能力的有效授权')
    if payload.valid_to <= _now():
        raise ApiException(422, "VALIDATION_FAILED", "授权结束时间必须晚于当前时间")
    person = session.get(Person, payload.person_id)
    if person is None or person.status != "active":
        raise ApiException(422, "VALIDATION_FAILED", "授权对象不存在或当前不可用")
    grant = CredentialGrant(
        credential_id=credential.id,
        person_id=person.id,
        capability=payload.capability,
        valid_to=payload.valid_to,
        reason=payload.reason,
    )
    session.add(grant)
    credential.version += 1
    credential.updated_at = _now()
    session.flush()
    _audit(
        session,
        resource_id=credential.resource_id,
        actor_id=actor_id,
        request_id=request_id,
        event_type="credential_grant_created",
        safe_after={"credential_id": str(credential.id), "person_id": str(person.id), "capability": grant.capability, "valid_to": grant.valid_to.isoformat()},
    )
    session.commit()
    session.refresh(grant)
    return grant


def reveal_credential(
    session: Session,
    settings: Settings,
    credential_id: UUID,
    payload: CredentialRevealRequest,
    *,
    actor_id: UUID,
    request_id: UUID,
) -> str:
    credential = session.get(CredentialRef, credential_id)
    if credential is None or credential.status != "saved" or credential.ciphertext is None or credential.nonce is None or credential.key_version is None:
        raise ApiException(404, "RESOURCE_NOT_FOUND", "凭据不存在或不可见")
    get_resource(session, credential.resource_id)
    now = _now()
    grant = session.scalar(
        select(CredentialGrant).where(
            CredentialGrant.credential_id == credential.id,
            CredentialGrant.person_id == actor_id,
            CredentialGrant.capability.in_(["view", "rotate"]),
            CredentialGrant.valid_from <= now,
            (CredentialGrant.valid_to.is_(None) | (CredentialGrant.valid_to > now)),
        )
    )
    if grant is None:
        raise ApiException(403, "PERMISSION_DENIED", "当前主体没有凭据查看授权")
    _audit(
        session,
        resource_id=credential.resource_id,
        actor_id=actor_id,
        request_id=request_id,
        event_type="credential_revealed",
        safe_after={"credential_id": str(credential.id), "grant_id": str(grant.id), "reason": payload.reason},
    )
    # Commit the access audit before releasing the plaintext. Any audit failure stops the reveal.
    session.commit()
    return decrypt_secret(
        settings,
        ciphertext=credential.ciphertext,
        nonce=credential.nonce,
        key_version=credential.key_version,
        associated_data=f"credential:{credential.id}".encode(),
    )
