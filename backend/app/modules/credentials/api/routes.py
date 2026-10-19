from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.modules.credentials.api.schemas import (
    CredentialAttachRequest,
    CredentialGrantCreate,
    CredentialGrantView,
    CredentialOperationView,
    CredentialRevealRequest,
    CredentialRevealView,
    SafeOperationResult,
    SecretStageCreate,
    SecretStageView,
)
from app.modules.credentials.application.service import (
    attach_credential,
    create_credential_grant,
    create_secret_stage,
    reveal_credential,
)
from app.modules.identity_access.public import PolicySubject, require_capability
from app.platform.db.session import database_session
from app.platform.http.errors import ApiException
from app.platform.http.schemas import ResponseMeta, SuccessEnvelope

router = APIRouter(tags=["credentials"])
SessionDependency = Annotated[Session, Depends(database_session)]
WriteSubject = Annotated[PolicySubject, Depends(require_capability("credential.write"))]
ReadSubject = Annotated[PolicySubject, Depends(require_capability("credential.read"))]
GrantSubject = Annotated[PolicySubject, Depends(require_capability("credential.grant"))]


def _actor(subject: PolicySubject) -> UUID:
    if not subject.subject_id:
        raise ApiException(401, "AUTHENTICATION_REQUIRED", "请先登录")
    try:
        return UUID(subject.subject_id)
    except ValueError:
        raise ApiException(401, "AUTHENTICATION_REQUIRED", "当前主体 ID 无效") from None


def _request_id(request: Request) -> UUID:
    return UUID(str(request.state.request_id))


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(request_id=request.state.request_id)


@router.post("/secret-stages", response_model=SuccessEnvelope[SecretStageView], status_code=201)
def create_secret_stage_route(
    request: Request,
    payload: SecretStageCreate,
    _subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[SecretStageView]:
    stage, token = create_secret_stage(session, request.app.state.settings, payload)
    return SuccessEnvelope(
        data=SecretStageView(stage_token=token, expires_at=stage.expires_at),
        error=None,
        meta=_meta(request),
    )


@router.post(
    "/resources/{resource_id}/credentials",
    response_model=SuccessEnvelope[CredentialOperationView],
    status_code=202,
)
def attach_credential_route(
    request: Request,
    resource_id: UUID,
    payload: CredentialAttachRequest,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[CredentialOperationView]:
    credential_id = attach_credential(
        session,
        request.app.state.settings,
        resource_id,
        payload,
        actor_id=_actor(subject),
        request_id=_request_id(request),
    )
    data = CredentialOperationView(
        operation_id=credential_id,
        status="succeeded",
        safe_result=SafeOperationResult(resource_id=resource_id, credential_id=credential_id, credential_status="saved"),
        retryable=False,
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.post(
    "/credentials/{credential_id}/actions/reveal",
    response_model=SuccessEnvelope[CredentialRevealView],
)
def reveal_credential_route(
    request: Request,
    response: Response,
    credential_id: UUID,
    payload: CredentialRevealRequest,
    subject: ReadSubject,
    session: SessionDependency,
) -> SuccessEnvelope[CredentialRevealView]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    value = reveal_credential(
        session,
        request.app.state.settings,
        credential_id,
        payload,
        actor_id=_actor(subject),
        request_id=_request_id(request),
    )
    return SuccessEnvelope(data=CredentialRevealView(secret_value=value), error=None, meta=_meta(request))


@router.post(
    "/credentials/{credential_id}/grants",
    response_model=SuccessEnvelope[CredentialGrantView],
    status_code=201,
)
def create_credential_grant_route(
    request: Request,
    credential_id: UUID,
    payload: CredentialGrantCreate,
    subject: GrantSubject,
    session: SessionDependency,
) -> SuccessEnvelope[CredentialGrantView]:
    grant = create_credential_grant(
        session,
        credential_id,
        payload,
        actor_id=_actor(subject),
        request_id=_request_id(request),
    )
    data = CredentialGrantView(
        id=grant.id,
        credential_id=grant.credential_id,
        person_id=grant.person_id,
        capability=grant.capability,
        valid_from=grant.valid_from,
        valid_to=grant.valid_to,
        reason=grant.reason,
        version=grant.version,
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))
