from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.platform.http.schemas import StrictModel


class BasicSubscriptionSummary(StrictModel):
    id: UUID
    plan: str | None
    seats_total: int | None
    seats_assigned: int | None
    billing_cycle: str | None
    starts_on: str | None
    ends_on: str | None


class ResourceType(StrEnum):
    platform_account = "platform_account"
    mailbox_account = "mailbox_account"
    api_key = "api_key"
    service_subscription = "service_subscription"
    business_space = "business_space"
    application = "application"
    api_service = "api_service"
    cloud_resource = "cloud_resource"
    domain = "domain"


class Lifecycle(StrEnum):
    unknown = "unknown"
    in_use = "in_use"
    disabled = "disabled"
    retired = "retired"


class Verification(StrEnum):
    unverified = "unverified"
    verified = "verified"
    needs_review = "needs_review"


class UsageMode(StrEnum):
    normal = "normal"
    test = "test"
    standby = "standby"


class PersonAssignmentCreate(StrictModel):
    person_id: UUID
    role: str = Field(pattern="^(owner|maintainer|use|controller)$")


class CompanyLinkCreate(StrictModel):
    company_id: UUID
    role: str = Field(pattern="^(owner|represented)$")


class RelationCreate(StrictModel):
    target_id: UUID
    relation_type: Literal["uses", "managed_by", "part_of", "contains", "depends_on"]
    note: str | None = Field(default=None, max_length=2000)


class ResourceRelationCreateRequest(StrictModel):
    expected_version: int = Field(ge=1)
    target_id: UUID
    relation_type: Literal["uses", "managed_by", "part_of", "contains", "depends_on"]
    note: str | None = Field(default=None, max_length=2000)


class VersionReasonRequest(StrictModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)


class MaterialCreate(StrictModel):
    kind: Literal["entry", "note", "attachment"]
    title: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    body: str | None = Field(default=None, max_length=20000)
    file_ref: str | None = Field(default=None, max_length=200)
    classification: str | None = Field(default=None, pattern="^(normal|restricted|sensitive)$")

    @model_validator(mode="after")
    def validate_kind_payload(self) -> "MaterialCreate":
        if self.kind == "entry" and (not self.url or not self.url.startswith(("http://", "https://"))):
            raise ValueError("入口资料必须使用 HTTP(S) URL")
        if self.kind == "note" and not self.body:
            raise ValueError("说明资料必须有正文")
        if self.kind == "attachment" and not self.file_ref:
            raise ValueError("附件资料必须引用已扫描文件")
        if self.kind != "entry" and self.url is not None:
            raise ValueError("只有入口资料可以填写 URL")
        return self


class BudgetEntry(StrictModel):
    amount: Decimal = Field(ge=0, decimal_places=2, max_digits=18)
    currency: str = Field(min_length=1, max_length=16)
    period: str = Field(min_length=1, max_length=32)
    meaning: str = Field(min_length=1, max_length=200)


class AccountInput(StrictModel):
    identifier: str | None = Field(default=None, max_length=320)
    login_methods: list[str] = Field(default_factory=list, max_length=6)
    account_role: str | None = Field(default=None, pattern="^(master|administrator|member|service|unknown)$")
    scope_label: str | None = Field(default=None, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=100)


class ResourceCreateRequest(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    type_code: ResourceType
    provider_name: str | None = Field(default=None, max_length=200)
    purpose: str | None = Field(default=None, max_length=2000)
    owning_department_id: UUID | None = None
    usage_mode: UsageMode | None = UsageMode.normal
    attributes: dict[str, Any] = Field(default_factory=dict)
    people: list[PersonAssignmentCreate] = Field(default_factory=list, max_length=200)
    company_links: list[CompanyLinkCreate] = Field(default_factory=list, max_length=100)
    relations: list[RelationCreate] = Field(default_factory=list, max_length=200)
    materials: list[MaterialCreate] = Field(default_factory=list, max_length=100)
    account: AccountInput | None = None
    platform_id: UUID | None = None
    source_note: str = Field(default="人工登记", min_length=1, max_length=500)
    lifecycle: Literal["unknown", "in_use"] = "unknown"

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("名称不能为空")
        return value


class AccountPatch(StrictModel):
    login_methods: list[str] | None = Field(default=None, max_length=6)
    account_role: str | None = Field(default=None, pattern="^(master|administrator|member|service|unknown)$")
    scope_label: str | None = Field(default=None, max_length=200)


class ResourcePatchChanges(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    provider_name: str | None = Field(default=None, max_length=200)
    purpose: str | None = Field(default=None, max_length=2000)
    usage_mode: UsageMode | None = None
    attributes: dict[str, Any] | None = None
    account: AccountPatch | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ResourcePatchChanges":
        if not self.model_fields_set:
            raise ValueError("至少需要一项可编辑字段")
        return self

    @field_validator("name")
    @classmethod
    def trim_patch_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("名称不能为空")
        return value


class ResourcePatchRequest(StrictModel):
    expected_version: int = Field(ge=1)
    changes: ResourcePatchChanges


class PersonSummary(StrictModel):
    id: UUID
    display_name: str


class OrganizationSummary(StrictModel):
    id: UUID
    display_name: str


class PersonAssignmentView(StrictModel):
    assignment_id: UUID
    person: PersonSummary
    role: str
    confirmation: str
    valid_from: datetime
    valid_to: datetime | None


class CompanyLinkView(StrictModel):
    assignment_id: UUID
    company: OrganizationSummary
    role: str
    confirmation: str
    valid_from: datetime
    valid_to: datetime | None


class AccountView(StrictModel):
    identifier: str | None
    login_methods: list[str]
    account_role: str | None = None
    scope_label: str | None = None
    aliases: list[str] = Field(default_factory=list)


class ResourceView(StrictModel):
    id: UUID
    code: str
    name: str
    type_code: ResourceType
    provider_name: str | None
    purpose: str | None
    owning_department: OrganizationSummary | None
    confirmed_company: OrganizationSummary | None
    owner: PersonSummary | None
    lifecycle: Lifecycle
    verification: Verification
    version: int
    updated_at: datetime
    people: list[PersonAssignmentView] = Field(default_factory=list)
    company_links: list[CompanyLinkView] = Field(default_factory=list)
    usage_mode: UsageMode | None
    visibility_scope: str
    attributes: dict[str, Any]
    account: AccountView | None
    credential_status: str = "not_saved"
    subscription_summary: BasicSubscriptionSummary | None = None
    missing_fields: list[str] = Field(default_factory=list)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    created_at: datetime
    platform_id: UUID | None = None


class ResourceSummary(StrictModel):
    id: UUID
    code: str
    name: str
    type_code: ResourceType
    provider_name: str | None
    purpose: str | None
    owning_department: OrganizationSummary | None
    confirmed_company: OrganizationSummary | None
    owner: PersonSummary | None
    lifecycle: Lifecycle
    verification: Verification
    version: int
    updated_at: datetime


class Pagination(StrictModel):
    page: int
    page_size: int
    total: int
    has_next: bool


class ResourcePage(StrictModel):
    items: list[ResourceSummary]
    pagination: Pagination


class MyResourceSummary(ResourceSummary):
    my_roles: list[str] = Field(default_factory=list)


class MyResourcePage(StrictModel):
    items: list[MyResourceSummary]
    pagination: Pagination


class ResourceRelationView(StrictModel):
    id: UUID
    source: ResourceSummary
    target: ResourceSummary
    relation_type: Literal["uses", "managed_by", "part_of", "contains", "depends_on"]
    direction: Literal["outgoing", "incoming"]
    confirmation: Literal["proposed", "confirmed"]
    valid_from: datetime
    valid_to: datetime | None
    note: str | None
    version: int


class RelationPage(StrictModel):
    items: list[ResourceRelationView]
    pagination: Pagination
    coverage: Literal["visible_known_relations"] = "visible_known_relations"
