from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.platform.http.schemas import StrictModel


class ContactKind(StrEnum):
    email = "email"
    phone = "phone"
    third_party = "third_party"


class BindingPurpose(StrEnum):
    registration = "registration"
    login = "login"
    recovery = "recovery"
    mfa = "mfa"


class ContactIdentityInput(StrictModel):
    kind: ContactKind
    value: str = Field(min_length=1, max_length=320)
    ownership: str = Field(pattern="^(company|personal|unknown)$")
    mailbox_account_id: UUID | None = None
    mailbox_association_role: Literal["alias"] | None = None
    custodian_person_id: UUID | None = None
    provider: str | None = Field(default=None,max_length=200)
    label: str | None = Field(default=None,max_length=200)
    company_id: UUID | None = None

    @field_validator("value")
    @classmethod
    def validate_email_shape(cls, value: str, info: object) -> str:
        # The protected store owns canonicalization; only reject obviously invalid email input here.
        if getattr(info, "data", {}).get("kind") == ContactKind.email and ("@" not in value or value.startswith("@")):
            raise ValueError("邮箱格式无效")
        return value

    @model_validator(mode="after")
    def validate_association_target(self) -> "ContactIdentityInput":
        if self.mailbox_account_id is not None and self.custodian_person_id is not None:
            raise ValueError("邮箱关联和直接保管人不能同时填写")
        if self.mailbox_account_id is not None and self.mailbox_association_role != "alias":
            raise ValueError("新增受管邮箱联系方式只能作为 alias 关联")
        if self.mailbox_association_role is not None and self.mailbox_account_id is None:
            raise ValueError("alias 关联必须指定邮箱账号")
        return self


class BindingCreateRequest(StrictModel):
    expected_version: int = Field(ge=1)
    purpose: BindingPurpose
    contact_identity_id: UUID | None = None
    contact: ContactIdentityInput | None = None

    @model_validator(mode="after")
    def require_one_contact_source(self) -> "BindingCreateRequest":
        if (self.contact_identity_id is None) == (self.contact is None):
            raise ValueError("必须选择已有联系方式或提交新的联系方式")
        return self


class ContactIdentityView(StrictModel):
    id: UUID
    kind: ContactKind
    masked_value: str
    ownership: str
    verification: str
    mailbox_account: object | None = None
    custodian: object | None = None


class BindingView(StrictModel):
    id: UUID
    account_resource_id: UUID
    contact: ContactIdentityView
    purpose: BindingPurpose
    confirmation: Literal["proposed", "confirmed"]
    valid_from: datetime
    valid_to: datetime | None
    version: int


class Pagination(StrictModel):
    page: int
    page_size: int
    total: int
    has_next: bool


class BindingPage(StrictModel):
    items: list[BindingView]
    pagination: Pagination


class MailboxContactIdentityOption(StrictModel):
    id: UUID
    kind: Literal["email"]
    masked_value: str
    ownership: str
    verification: str


class MailboxContactIdentityPage(StrictModel):
    items: list[MailboxContactIdentityOption]
    pagination: Pagination
