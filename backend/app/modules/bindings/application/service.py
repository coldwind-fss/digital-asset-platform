from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.bindings.api.schemas import BindingCreateRequest
from app.platform.db.models import (
    Account,
    AccountBinding,
    ContactIdentity,
    MailboxContactAssociation,
    Resource,
)
from app.platform.http.errors import ApiException


def _masked(contact: ContactIdentity) -> str:
    return contact.masked_value or "已保护联系方式"


def get_account_resource(session: Session, resource_id: UUID) -> Resource:
    resource = session.get(Resource, resource_id)
    if resource is None or resource.archived_at is not None:
        raise ApiException(404, "RESOURCE_NOT_FOUND", "资源不存在或不可见")
    if session.get(Account, resource_id) is None:
        raise ApiException(422, "VALIDATION_FAILED", "联系方式绑定只适用于账号资源")
    return resource


def list_bindings(
    session: Session,
    resource_id: UUID,
    *,
    include_history: bool,
    page: int,
    page_size: int,
) -> tuple[list[AccountBinding], int]:
    get_account_resource(session, resource_id)
    conditions = [AccountBinding.account_resource_id == resource_id, AccountBinding.confirmation != "rejected"]
    if not include_history:
        conditions.append(AccountBinding.valid_to.is_(None))
    statement = select(AccountBinding).where(*conditions).order_by(AccountBinding.valid_from.desc(), AccountBinding.id)
    total = int(session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    return list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()), total


def create_binding(session: Session, resource_id: UUID, payload: BindingCreateRequest) -> AccountBinding:
    from app.platform.db.commands import write_resource
    resource = write_resource(session,resource_id,payload.expected_version)
    get_account_resource(session,resource_id)
    if resource.version != payload.expected_version:
        raise ApiException(409, "STATE_CONFLICT", "账号资源已被其他操作更新，请刷新后重试")
    if payload.contact is not None:
        from app.modules.bindings.application.identities import create_contact_identity
        contact = create_contact_identity(session,kind=payload.contact.kind.value,value=payload.contact.value,ownership=payload.contact.ownership.value,custodian_person_id=payload.contact.custodian_person_id,provider=payload.contact.provider,label=payload.contact.label,company_id=payload.contact.company_id)
        if payload.contact.mailbox_account_id:
            mailbox=write_resource(session,payload.contact.mailbox_account_id)
            if mailbox.type_code!='mailbox_account' or contact.kind!='email':raise ApiException(422,'VALIDATION_FAILED','别名必须关联真实邮箱账号与邮箱身份')
            session.add(MailboxContactAssociation(mailbox_account_id=mailbox.id,contact_identity_id=contact.id,role='alias',confirmation='proposed'))
    else:
        contact = session.get(ContactIdentity, payload.contact_identity_id)
    if contact is None:
        raise ApiException(404, "REFERENCE_NOT_FOUND", "联系方式不存在或不可见")
    duplicate = session.scalar(
        select(AccountBinding.id).where(
            AccountBinding.account_resource_id == resource_id,
            AccountBinding.contact_identity_id == contact.id,
            AccountBinding.purpose == payload.purpose.value,
            AccountBinding.confirmation != "rejected",
            AccountBinding.valid_to.is_(None),
        )
    )
    if duplicate is not None:
        raise ApiException(409, "STATE_CONFLICT", "当前账号已经存在相同用途的联系方式绑定")
    binding = AccountBinding(
        account_resource_id=resource_id,
        contact_identity_id=contact.id,
        purpose=payload.purpose.value,
        confirmation="proposed",
    )
    session.add(binding)
    resource.version += 1
    resource.updated_at = datetime.now(UTC)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiException(409, "STATE_CONFLICT", "联系方式绑定与已有数据冲突") from None
    session.refresh(binding)
    return binding


def get_contact(session: Session, contact_id: UUID) -> ContactIdentity:
    contact = session.get(ContactIdentity, contact_id)
    if contact is None:
        raise ApiException(404, "REFERENCE_NOT_FOUND", "联系方式不存在或不可见")
    return contact


def list_mailbox_contacts(
    session: Session,
    resource_id: UUID,
    *,
    page: int,
    page_size: int,
) -> tuple[list[ContactIdentity], int]:
    resource = get_account_resource(session, resource_id)
    if resource.type_code != "mailbox_account":
        raise ApiException(404, "RESOURCE_NOT_FOUND", "资源不存在或不可见")
    statement = (
        select(ContactIdentity)
        .join(MailboxContactAssociation, MailboxContactAssociation.contact_identity_id == ContactIdentity.id)
        .where(
            MailboxContactAssociation.mailbox_account_id == resource_id,
            MailboxContactAssociation.valid_to.is_(None),
            MailboxContactAssociation.confirmation != "rejected",
            ContactIdentity.kind == "email",
        )
        .order_by(MailboxContactAssociation.role.asc(), ContactIdentity.id.asc())
    )
    total = int(session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    return list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()), total
