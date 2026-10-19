from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.modules.bindings.api.schemas import (
    BindingCreateRequest,
    BindingPage,
    BindingView,
    ContactIdentityView,
    MailboxContactIdentityPage,
    MailboxContactIdentityOption,
    Pagination,
)
from app.modules.bindings.application.service import (
    create_binding,
    get_contact,
    list_bindings,
    list_mailbox_contacts,
)
from app.modules.identity_access.public import PolicySubject, require_capability
from app.platform.db.models import AccountBinding
from app.platform.db.session import database_session
from app.platform.http.pagination import PageSize
from app.platform.http.schemas import ResponseMeta, SuccessEnvelope

router = APIRouter(tags=["resources"])
SessionDependency = Annotated[Session, Depends(database_session)]
ReadSubject = Annotated[PolicySubject, Depends(require_capability("binding.read"))]
WriteSubject = Annotated[PolicySubject, Depends(require_capability("binding.write"))]
def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(request_id=request.state.request_id)


def _contact_view(session: Session, contact_id: UUID) -> ContactIdentityView:
    contact = get_contact(session, contact_id)
    return ContactIdentityView(
        id=contact.id,
        kind=contact.kind,
        masked_value=contact.masked_value or "已保护联系方式",
        ownership=contact.ownership,
        verification=contact.verification,
    )


def _binding_view(session: Session, binding: AccountBinding) -> BindingView:
    return BindingView(
        id=binding.id,
        account_resource_id=binding.account_resource_id,
        contact=_contact_view(session, binding.contact_identity_id),
        purpose=binding.purpose,
        confirmation=binding.confirmation,
        valid_from=binding.valid_from,
        valid_to=binding.valid_to,
        version=binding.version,
    )


@router.get("/resources/{resource_id}/bindings", response_model=SuccessEnvelope[BindingPage])
def list_resource_bindings_route(
    request: Request,
    resource_id: UUID,
    _subject: ReadSubject,
    session: SessionDependency,
    include_history: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[BindingPage]:
    rows, total = list_bindings(session, resource_id, include_history=include_history, page=page, page_size=page_size)
    data = BindingPage(
        items=[_binding_view(session, row) for row in rows],
        pagination=Pagination(page=page, page_size=page_size, total=total, has_next=page * page_size < total),
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.post("/resources/{resource_id}/bindings", response_model=SuccessEnvelope[BindingView], status_code=201)
def create_resource_binding_route(
    request: Request,
    resource_id: UUID,
    payload: BindingCreateRequest,
    _subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[BindingView]:
    binding = create_binding(session, resource_id, payload)
    return SuccessEnvelope(data=_binding_view(session, binding), error=None, meta=_meta(request))


@router.get(
    "/resources/{resource_id}/contact-identities",
    response_model=SuccessEnvelope[MailboxContactIdentityPage],
)
def list_mailbox_contact_identities_route(
    request: Request,
    resource_id: UUID,
    _subject: ReadSubject,
    session: SessionDependency,
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[MailboxContactIdentityPage]:
    rows, total = list_mailbox_contacts(session, resource_id, page=page, page_size=page_size)
    data = MailboxContactIdentityPage(
        items=[
            MailboxContactIdentityOption(
                id=contact.id,
                kind="email",
                masked_value=contact.masked_value or "已保护联系方式",
                ownership=contact.ownership,
                verification=contact.verification,
            )
            for contact in rows
        ],
        pagination=Pagination(page=page, page_size=page_size, total=total, has_next=page * page_size < total),
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))
