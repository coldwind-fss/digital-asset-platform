from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_column(*, primary_key: bool = False, nullable: bool = False) -> Mapped[UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=primary_key, nullable=nullable, default=uuid4)


def created_at_column() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class InstanceMetadata(Base):
    __tablename__ = "instance_metadata"
    __table_args__ = (CheckConstraint("singleton_key = 1", name="ck_instance_metadata_singleton"),)

    singleton_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_family: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class Department(Base):
    __tablename__ = "department"
    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_department_not_self_parent"),
        CheckConstraint("status IN ('active', 'inactive', 'unknown')", name="ck_department_status"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    parent_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("department.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class Person(Base):
    __tablename__ = "person"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'unknown')", name="ck_person_status"),
        UniqueConstraint("external_namespace", "stable_external_id", name="uq_person_external_identity"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    external_namespace: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stable_external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    department_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("department.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'unknown'"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class Company(Base):
    __tablename__ = "company"
    __table_args__ = (CheckConstraint("status IN ('active', 'inactive', 'unknown')", name="ck_company_status"),)

    id: Mapped[UUID] = uuid_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_by_person_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    registration_identifier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'unknown'"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class Resource(Base):
    __tablename__ = "resource"
    __table_args__ = (
        CheckConstraint(
            "type_code IN ('platform_account', 'mailbox_account', 'api_key', 'service_subscription', 'business_space', 'application', 'api_service', 'cloud_resource', 'domain')",
            name="ck_resource_type_code",
        ),
        CheckConstraint("lifecycle IN ('unknown', 'in_use', 'disabled', 'retired')", name="ck_resource_lifecycle"),
        CheckConstraint("verification IN ('unverified', 'verified', 'needs_review')", name="ck_resource_verification"),
        CheckConstraint("usage_mode IN ('normal', 'test', 'standby')", name="ck_resource_usage_mode"),
        CheckConstraint("visibility_scope IN ('restricted', 'department', 'company')", name="ck_resource_visibility_scope"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type_code: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    owning_department_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("department.id"), nullable=True)
    created_by_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    platform_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("platform.id"), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'unknown'"))
    verification: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'unverified'"))
    usage_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'normal'"))
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    visibility_scope: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'restricted'"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        CheckConstraint(
            "account_role IN ('master', 'administrator', 'member', 'service', 'unknown')",
            name="ck_account_role",
        ),
    )

    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), primary_key=True)
    identifier_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    identifier_nonce: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    identifier_masked: Mapped[str | None] = mapped_column(String(200), nullable=True)
    identifier_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    key_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    login_methods: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, server_default=text("ARRAY['unknown']::varchar[]")
    )
    account_role: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'unknown'"))
    scope_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class ResourcePerson(Base):
    __tablename__ = "resource_person"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'maintainer', 'use', 'controller')",
            name="ck_resource_person_role",
        ),
        CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_resource_person_confirmation"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_resource_person_valid_range"),
        UniqueConstraint("resource_id", "person_id", "role", "valid_from", name="uq_resource_person_interval"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=False)
    person_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmation: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'proposed'"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class ResourceCompany(Base):
    __tablename__ = "resource_company"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'represented')", name="ck_resource_company_role"),
        CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_resource_company_confirmation"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_resource_company_valid_range"),
        UniqueConstraint("resource_id", "company_id", "role", "valid_from", name="uq_resource_company_interval"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("company.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmation: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'proposed'"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class ResourceRelation(Base):
    __tablename__ = "resource_relation"
    __table_args__ = (
        CheckConstraint("source_resource_id <> target_resource_id", name="ck_resource_relation_not_self"),
        CheckConstraint("relation_type IN ('uses', 'managed_by', 'part_of', 'contains', 'depends_on')", name="ck_resource_relation_type"),
        CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_resource_relation_confirmation"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_resource_relation_valid_range"),
        UniqueConstraint(
            "source_resource_id", "target_resource_id", "relation_type", "valid_from", name="uq_resource_relation_interval"
        ),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    source_resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=False)
    target_resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmation: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'proposed'"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class ContactIdentity(Base):
    __tablename__ = "contact_identity"
    __table_args__ = (
        CheckConstraint("kind IN ('email', 'phone', 'third_party')", name="ck_contact_identity_kind"),
        CheckConstraint("ownership IN ('company', 'personal', 'unknown')", name="ck_contact_identity_ownership"),
        CheckConstraint("verification IN ('unverified', 'verified', 'needs_review')", name="ck_contact_identity_verification"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    protected_value: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    nonce: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("company.id"), nullable=True)
    created_by_person_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=True)
    key_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    masked_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ownership: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'unknown'"))
    custodian_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    verification: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'unverified'"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class MailboxContactAssociation(Base):
    __tablename__ = "mailbox_contact_association"
    __table_args__ = (
        CheckConstraint("role IN ('primary', 'alias')", name="ck_mailbox_contact_role"),
        CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_mailbox_contact_confirmation"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_mailbox_contact_valid_range"),
        UniqueConstraint(
            "mailbox_account_id", "contact_identity_id", "role", "valid_from", name="uq_mailbox_contact_interval"
        ),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    mailbox_account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("account.resource_id"), nullable=False)
    contact_identity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contact_identity.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmation: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'proposed'"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class AccountBinding(Base):
    __tablename__ = "account_binding"
    __table_args__ = (
        CheckConstraint("purpose IN ('registration', 'login', 'recovery', 'mfa')", name="ck_account_binding_purpose"),
        CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_account_binding_confirmation"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_account_binding_valid_range"),
        UniqueConstraint(
            "account_resource_id", "contact_identity_id", "purpose", "valid_from", name="uq_account_binding_interval"
        ),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    account_resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("account.resource_id"), nullable=False)
    contact_identity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contact_identity.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmation: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'proposed'"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class CredentialRef(Base):
    __tablename__ = "credential_ref"
    __table_args__ = (
        CheckConstraint("kind IN ('password', 'api_key', 'certificate_pin', 'other')", name="ck_credential_ref_kind"),
        CheckConstraint("status IN ('not_saved', 'pending', 'saved', 'failed', 'superseded', 'revoked')", name="ck_credential_ref_status"),
        CheckConstraint(
            "(status IN ('saved','superseded','revoked') AND ciphertext IS NOT NULL AND nonce IS NOT NULL AND key_version IS NOT NULL) OR "
            "(status NOT IN ('saved','superseded','revoked') AND ciphertext IS NULL AND nonce IS NULL)",
            name="ck_credential_ref_material_state",
        ),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'not_saved'"))
    ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    nonce: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    key_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class CredentialGrant(Base):
    __tablename__ = "credential_grant"
    __table_args__ = (
        CheckConstraint("capability IN ('view', 'rotate')", name="ck_credential_grant_capability"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_credential_grant_valid_range"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    credential_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("credential_ref.id"), nullable=False)
    person_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=False)
    capability: Mapped[str] = mapped_column(String(16), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class CredentialStage(Base):
    __tablename__ = "credential_stage"
    __table_args__ = (
        CheckConstraint("kind IN ('password', 'api_key', 'certificate_pin', 'other')", name="ck_credential_stage_kind"),
        CheckConstraint("consumed_at IS NULL OR consumed_at >= created_at", name="ck_credential_stage_consumed_range"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    created_by_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'attach'"))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class SubscriptionProfile(Base):
    __tablename__ = "subscription_profile"
    __table_args__ = (CheckConstraint("renewal_day IS NULL OR renewal_day BETWEEN 1 AND 31", name="ck_subscription_renewal_day"),)

    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), primary_key=True)
    plan: Mapped[str | None] = mapped_column(String(200), nullable=True)
    renewal_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    settlement_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)


class SubscriptionBudget(Base):
    __tablename__ = "subscription_budget"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_subscription_budget_position"),
        CheckConstraint("amount >= 0", name="ck_subscription_budget_amount"),
        UniqueConstraint("resource_id", "position", name="uq_subscription_budget_position"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("subscription_profile.resource_id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[str] = mapped_column(String(32), nullable=False)
    meaning: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class Material(Base):
    __tablename__ = "material"
    __table_args__ = (
        CheckConstraint("kind IN ('entry', 'note', 'attachment')", name="ck_material_kind"),
        CheckConstraint("classification IN ('normal', 'restricted', 'sensitive')", name="ck_material_classification"),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    classification: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'normal'"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class ChangeCase(Base):
    __tablename__ = "change_case"
    __table_args__ = (
        CheckConstraint("case_type IN ('change', 'transfer', 'offboard')", name="ck_change_case_type"),
        CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'completed_with_exceptions', 'cancelled')",
            name="ck_change_case_status",
        ),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    created_by_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    case_type: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    coordinator_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'draft'"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class ChangeItem(Base):
    __tablename__ = "change_item"
    __table_args__ = (
        CheckConstraint(
            "action IN ('change_owner', 'change_organization', 'change_visibility', 'grant_use', 'remove_use', 'transfer_controller', 'change_binding', 'change_mailbox_address', 'change_management_relation', 'disable_resource', 'retire_resource', 'reactivate_resource', 'rotate_credential', 'revoke_credential_grant', 'revoke_credential', 'replace_key')",
            name="ck_change_item_action",
        ),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'awaiting_confirmation', 'completed', 'cancelled', 'failed', 'cancellation_requested')",
            name="ck_change_item_status",
        ),
        CheckConstraint(
            "(CASE WHEN resource_person_id IS NULL THEN 0 ELSE 1 END) + "
            "(CASE WHEN account_binding_id IS NULL THEN 0 ELSE 1 END) + "
            "(CASE WHEN resource_relation_id IS NULL THEN 0 ELSE 1 END) <= 1",
            name="ck_change_item_single_target",
        ),
    )

    id: Mapped[UUID] = uuid_column(primary_key=True)
    case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("change_case.id"), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    assignee_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    resource_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource_person.id"), nullable=True)
    account_binding_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("account_binding.id"), nullable=True)
    resource_relation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource_relation.id"), nullable=True)
    from_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    to_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    proposal_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    execution_history: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    executed_by_person_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=True)
    cancellation_requested_by: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=True)
    new_contact_identity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("contact_identity.id"), nullable=True)
    replacement_resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=True)
    expected_resource_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_target_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'pending'"))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_material_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("material.id"), nullable=True)
    non_secret_result: Mapped[str | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class ChangeRelationDetail(Base):
    __tablename__ = "change_relation_detail"

    item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("change_item.id"), primary_key=True)
    relation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource_relation.id"), nullable=False)
    proposed_target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("resource.id"), nullable=True)
    change_item_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("change_item.id"), nullable=True)
    actor_person_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=True)
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'system'"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = created_at_column()
    safe_before: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    safe_after: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class Platform(Base):
    __tablename__ = "platform"
    __table_args__ = (CheckConstraint("status IN ('active', 'inactive', 'unknown')", name="ck_platform_status"),)
    id: Mapped[UUID] = uuid_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'unknown'"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class AuthAccount(Base):
    __tablename__ = "auth_account"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'resource_manager', 'member')", name="ck_auth_account_role"),
        CheckConstraint("status IN ('pending', 'active', 'inactive')", name="ck_auth_account_status"),
        CheckConstraint("username = lower(username)", name="ck_auth_account_username_lower"),
        CheckConstraint("status <> 'active' OR password_hash IS NOT NULL", name="ck_auth_account_active_password"),
    )
    id: Mapped[UUID] = uuid_column(primary_key=True)
    person_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("person.id"), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'member'"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class AuthSession(Base):
    __tablename__ = "auth_session"
    id: Mapped[UUID] = uuid_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("auth_account.id"), nullable=False, index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class AuthScope(Base):
    __tablename__ = "auth_scope"
    __table_args__ = (
        CheckConstraint("kind IN ('department', 'resource')", name="ck_auth_scope_kind"),
        CheckConstraint("permission IN ('read', 'manage')", name="ck_auth_scope_permission"),
        UniqueConstraint("account_id", "kind", "target_id", name="uq_auth_scope_target"),
    )
    id: Mapped[UUID] = uuid_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("auth_account.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    permission: Mapped[str] = mapped_column(String(16), nullable=False)


class AuthActionToken(Base):
    __tablename__ = "auth_action_token"
    __table_args__ = (CheckConstraint("purpose IN ('activate', 'recover')", name="ck_auth_action_token_purpose"),)
    id: Mapped[UUID] = uuid_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("auth_account.id"), nullable=False, index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class AuthThrottle(Base):
    __tablename__ = "auth_throttle"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RelationDeclaration(Base):
    __tablename__ = "relation_declaration"
    __table_args__ = (CheckConstraint("state IN ('unknown','not_applicable','verified_absent')", name="ck_relation_declaration_state"),)
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    relation_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class ProvenanceEntry(Base):
    __tablename__ = "provenance_entry"
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_person_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class IdempotencyReceipt(Base):
    __tablename__ = "idempotency_receipt"
    __table_args__ = (UniqueConstraint("person_id","route_key","key",name="uq_idempotency_receipt"),)
    id: Mapped[UUID] = uuid_column(primary_key=True)
    person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=False)
    route_key: Mapped[str] = mapped_column(String(300), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class CredentialOperation(Base):
    __tablename__ = "credential_operation"
    __table_args__ = (CheckConstraint("status IN ('prepared','applied','cancelled')", name="ck_credential_operation_status"),)
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    credential_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("credential_ref.id"), nullable=False)
    stage_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("credential_stage.id"), nullable=True)
    grant_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("credential_grant.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_credential_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'prepared'"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result_credential_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("credential_ref.id"), nullable=True)
    ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    nonce: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    key_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class SubscriptionLedger(Base):
    __tablename__ = "subscription_ledger"
    __table_args__ = (UniqueConstraint("resource_id"),CheckConstraint("seats_total IS NULL OR seats_total >= 0",name="ck_ledger_seats"))
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    plan: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seats_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seats_assigned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    billing_cycle: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'month'"))
    reminder_days: Mapped[list[int]] = mapped_column(JSONB, nullable=False, server_default=text("'[30,7,1]'::jsonb"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = created_at_column()


class SubscriptionPeriod(Base):
    __tablename__ = "subscription_period"
    __table_args__ = (CheckConstraint("ends_on >= starts_on",name="ck_period_dates"),CheckConstraint("planned_amount IS NULL OR planned_amount >= 0",name="ck_period_amount"))
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    ledger_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("subscription_ledger.id"), nullable=False)
    starts_on: Mapped[datetime] = mapped_column(Date, nullable=False)
    ends_on: Mapped[datetime] = mapped_column(Date, nullable=False)
    planned_amount: Mapped[object | None] = mapped_column(Numeric(18,2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()


class ExpenseEntry(Base):
    __tablename__ = "expense_entry"
    __table_args__ = (CheckConstraint("amount >= 0",name="ck_expense_amount"),CheckConstraint("kind IN ('actual','budget')",name="ck_expense_kind"))
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    ledger_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("subscription_ledger.id"), nullable=False)
    period_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("subscription_period.id"), nullable=True)
    corrects_entry_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("expense_entry.id"), nullable=True)
    amount: Mapped[object] = mapped_column(Numeric(18,2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_on: Mapped[datetime] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()


class ReminderItem(Base):
    __tablename__ = "reminder_item"
    __table_args__ = (UniqueConstraint("period_id","window_days",name="uq_reminder_window"),)
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    period_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("subscription_period.id"), nullable=True)
    due_on: Mapped[datetime] = mapped_column(Date, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime] = created_at_column()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReminderRead(Base):
    __tablename__ = "reminder_read"
    __table_args__ = (UniqueConstraint("reminder_id","person_id",name="uq_reminder_read"),)
    id: Mapped[UUID] = uuid_column(primary_key=True)
    reminder_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("reminder_item.id"), nullable=False)
    person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class PlatformConnection(Base):
    __tablename__ = "platform_connection"
    __table_args__ = (CheckConstraint("provider = 'deepseek'",name="ck_connection_provider"),CheckConstraint("interval_seconds >= 3600",name="ck_connection_interval"))
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    credential_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("credential_ref.id"), nullable=False)
    credential_version: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'active'"))
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("21600"))
    scheduled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()


class SyncJob(Base):
    __tablename__ = "sync_job"
    __table_args__ = (UniqueConstraint("connection_id","dedupe_key",name="uq_sync_job_trigger"),)
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("platform_connection.id"), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshot"
    __table_args__ = (UniqueConstraint("job_id","currency",name="uq_snapshot_job_currency"),)
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("platform_connection.id"), nullable=False)
    job_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("sync_job.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_balance: Mapped[object] = mapped_column(Numeric(24,8), nullable=False)
    granted_balance: Mapped[object] = mapped_column(Numeric(24,8), nullable=False)
    topped_up_balance: Mapped[object] = mapped_column(Numeric(24,8), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    collected_at: Mapped[datetime] = created_at_column()


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeat"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PrivateFile(Base):
    __tablename__ = "private_file"
    id: Mapped[UUID] = uuid_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("resource.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'available'"))
    classification: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'normal'"))
    check_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    replaces_file_id: Mapped[UUID | None] = mapped_column(Uuid(), ForeignKey("private_file.id"), nullable=True)
    created_by_person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportBatch(Base):
    __tablename__ = "import_batch"
    id: Mapped[UUID] = uuid_column(primary_key=True)
    created_by_person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), nullable=False)
    type_code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    rows: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    results: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'preview'"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_at_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preference"
    person_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("person.id"), primary_key=True)
    show_due: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
