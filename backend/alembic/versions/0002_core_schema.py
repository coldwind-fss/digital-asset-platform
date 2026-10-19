"""Create the Digital Asset Platform resource/account core schema.

This migration intentionally contains metadata and relationship structures only.
Credential material is not persisted here; the credential boundary is introduced
by the later credential-operations SPEC.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_core_schema"
down_revision = "0001_instance"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def timestamp_column(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)


def uuid_column(name: str, *, nullable: bool = False, primary_key: bool = False) -> sa.Column:
    return sa.Column(name, UUID, nullable=nullable, primary_key=primary_key)


def upgrade() -> None:
    op.create_table(
        "department",
        uuid_column("id", primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("parent_id", UUID, sa.ForeignKey("department.id"), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_department_not_self_parent"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'unknown')", name="ck_department_status"),
    )
    op.create_table(
        "person",
        uuid_column("id", primary_key=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("external_namespace", sa.String(length=100), nullable=True),
        sa.Column("stable_external_id", sa.String(length=200), nullable=True),
        sa.Column("department_id", UUID, sa.ForeignKey("department.id"), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'unknown'"), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'unknown')", name="ck_person_status"),
        sa.UniqueConstraint("external_namespace", "stable_external_id", name="uq_person_external_identity"),
    )
    op.create_table(
        "company",
        uuid_column("id", primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("registration_identifier", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'unknown'"), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'unknown')", name="ck_company_status"),
    )
    op.create_table(
        "resource",
        uuid_column("id", primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type_code", sa.String(length=32), nullable=False),
        sa.Column("provider_name", sa.String(length=200), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("owning_department_id", UUID, sa.ForeignKey("department.id"), nullable=True),
        sa.Column("lifecycle", sa.String(length=16), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("verification", sa.String(length=16), server_default=sa.text("'unverified'"), nullable=False),
        sa.Column("usage_mode", sa.String(length=16), server_default=sa.text("'normal'"), nullable=False),
        sa.Column("attributes", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("visibility_scope", sa.String(length=16), server_default=sa.text("'restricted'"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint(
            "type_code IN ('platform_account', 'mailbox_account', 'api_key', 'service_subscription', 'business_space', 'application')",
            name="ck_resource_type_code",
        ),
        sa.CheckConstraint("lifecycle IN ('unknown', 'in_use', 'disabled', 'retired')", name="ck_resource_lifecycle"),
        sa.CheckConstraint("verification IN ('unverified', 'verified', 'needs_review')", name="ck_resource_verification"),
        sa.CheckConstraint("usage_mode IN ('normal', 'test', 'standby')", name="ck_resource_usage_mode"),
        sa.CheckConstraint("visibility_scope IN ('restricted', 'department', 'company')", name="ck_resource_visibility_scope"),
        sa.UniqueConstraint("code", name="uq_resource_code"),
    )
    op.create_table(
        "account",
        uuid_column("resource_id", primary_key=True),
        sa.ForeignKeyConstraint(["resource_id"], ["resource.id"]),
        sa.Column("identifier_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("identifier_masked", sa.String(length=200), nullable=True),
        sa.Column("identifier_fingerprint", sa.LargeBinary(), nullable=True),
        sa.Column("key_version", sa.String(length=64), nullable=True),
        sa.Column("login_methods", postgresql.ARRAY(sa.String(length=32)), server_default=sa.text("ARRAY['unknown']::varchar[]"), nullable=False),
        sa.Column("account_role", sa.String(length=32), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("scope_label", sa.String(length=200), nullable=True),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint("account_role IN ('master', 'administrator', 'member', 'service', 'unknown')", name="ck_account_role"),
    )
    op.create_table(
        "resource_person",
        uuid_column("id", primary_key=True),
        sa.Column("resource_id", UUID, sa.ForeignKey("resource.id"), nullable=False),
        sa.Column("person_id", UUID, sa.ForeignKey("person.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("confirmation", sa.String(length=16), server_default=sa.text("'proposed'"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'maintainer', 'use', 'controller')", name="ck_resource_person_role"),
        sa.CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_resource_person_confirmation"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_resource_person_valid_range"),
        sa.UniqueConstraint("resource_id", "person_id", "role", "valid_from", name="uq_resource_person_interval"),
    )
    op.create_table(
        "resource_company",
        uuid_column("id", primary_key=True),
        sa.Column("resource_id", UUID, sa.ForeignKey("resource.id"), nullable=False),
        sa.Column("company_id", UUID, sa.ForeignKey("company.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("confirmation", sa.String(length=16), server_default=sa.text("'proposed'"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'represented')", name="ck_resource_company_role"),
        sa.CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_resource_company_confirmation"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_resource_company_valid_range"),
        sa.UniqueConstraint("resource_id", "company_id", "role", "valid_from", name="uq_resource_company_interval"),
    )
    op.create_table(
        "resource_relation",
        uuid_column("id", primary_key=True),
        sa.Column("source_resource_id", UUID, sa.ForeignKey("resource.id"), nullable=False),
        sa.Column("target_resource_id", UUID, sa.ForeignKey("resource.id"), nullable=False),
        sa.Column("relation_type", sa.String(length=16), nullable=False),
        sa.Column("confirmation", sa.String(length=16), server_default=sa.text("'proposed'"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("source_resource_id <> target_resource_id", name="ck_resource_relation_not_self"),
        sa.CheckConstraint("relation_type IN ('uses', 'managed_by', 'part_of')", name="ck_resource_relation_type"),
        sa.CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_resource_relation_confirmation"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_resource_relation_valid_range"),
        sa.UniqueConstraint("source_resource_id", "target_resource_id", "relation_type", "valid_from", name="uq_resource_relation_interval"),
    )
    op.create_table(
        "contact_identity",
        uuid_column("id", primary_key=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("protected_value", sa.LargeBinary(), nullable=True),
        sa.Column("key_version", sa.String(length=64), nullable=True),
        sa.Column("masked_value", sa.String(length=200), nullable=True),
        sa.Column("fingerprint", sa.LargeBinary(), nullable=True),
        sa.Column("ownership", sa.String(length=16), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("custodian_person_id", UUID, sa.ForeignKey("person.id"), nullable=True),
        sa.Column("verification", sa.String(length=16), server_default=sa.text("'unverified'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint("kind IN ('email', 'phone')", name="ck_contact_identity_kind"),
        sa.CheckConstraint("ownership IN ('company', 'personal', 'unknown')", name="ck_contact_identity_ownership"),
        sa.CheckConstraint("verification IN ('unverified', 'verified', 'needs_review')", name="ck_contact_identity_verification"),
    )
    op.create_table(
        "mailbox_contact_association",
        uuid_column("id", primary_key=True),
        sa.Column("mailbox_account_id", UUID, sa.ForeignKey("account.resource_id"), nullable=False),
        sa.Column("contact_identity_id", UUID, sa.ForeignKey("contact_identity.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("confirmation", sa.String(length=16), server_default=sa.text("'proposed'"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("role IN ('primary', 'alias')", name="ck_mailbox_contact_role"),
        sa.CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_mailbox_contact_confirmation"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_mailbox_contact_valid_range"),
        sa.UniqueConstraint("mailbox_account_id", "contact_identity_id", "role", "valid_from", name="uq_mailbox_contact_interval"),
    )
    op.create_table(
        "account_binding",
        uuid_column("id", primary_key=True),
        sa.Column("account_resource_id", UUID, sa.ForeignKey("account.resource_id"), nullable=False),
        sa.Column("contact_identity_id", UUID, sa.ForeignKey("contact_identity.id"), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("confirmation", sa.String(length=16), server_default=sa.text("'proposed'"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("purpose IN ('registration', 'login', 'recovery', 'mfa')", name="ck_account_binding_purpose"),
        sa.CheckConstraint("confirmation IN ('proposed', 'confirmed', 'rejected')", name="ck_account_binding_confirmation"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_account_binding_valid_range"),
        sa.UniqueConstraint("account_resource_id", "contact_identity_id", "purpose", "valid_from", name="uq_account_binding_interval"),
    )
    op.create_table(
        "subscription_profile",
        uuid_column("resource_id", primary_key=True),
        sa.ForeignKeyConstraint(["resource_id"], ["resource.id"]),
        sa.Column("plan", sa.String(length=200), nullable=True),
        sa.Column("renewal_day", sa.Integer(), nullable=True),
        sa.Column("expires_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_label", sa.String(length=200), nullable=True),
        sa.Column("settlement_mode", sa.String(length=32), nullable=True),
        sa.CheckConstraint("renewal_day IS NULL OR renewal_day BETWEEN 1 AND 31", name="ck_subscription_renewal_day"),
    )
    op.create_table(
        "subscription_budget",
        uuid_column("id", primary_key=True),
        sa.Column("resource_id", UUID, sa.ForeignKey("subscription_profile.resource_id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("period", sa.String(length=32), nullable=False),
        sa.Column("meaning", sa.String(length=200), nullable=False),
        timestamp_column("created_at"),
        sa.CheckConstraint("position >= 0", name="ck_subscription_budget_position"),
        sa.CheckConstraint("amount >= 0", name="ck_subscription_budget_amount"),
        sa.UniqueConstraint("resource_id", "position", name="uq_subscription_budget_position"),
    )
    op.create_table(
        "material",
        uuid_column("id", primary_key=True),
        sa.Column("resource_id", UUID, sa.ForeignKey("resource.id"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("file_ref", sa.String(length=200), nullable=True),
        sa.Column("classification", sa.String(length=16), server_default=sa.text("'normal'"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint("kind IN ('entry', 'note', 'attachment')", name="ck_material_kind"),
        sa.CheckConstraint("classification IN ('normal', 'restricted', 'sensitive')", name="ck_material_classification"),
    )
    op.create_table(
        "change_case",
        uuid_column("id", primary_key=True),
        sa.Column("case_type", sa.String(length=16), nullable=False),
        sa.Column("subject_person_id", UUID, sa.ForeignKey("person.id"), nullable=True),
        sa.Column("coordinator_person_id", UUID, sa.ForeignKey("person.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint("case_type IN ('change', 'transfer', 'offboard')", name="ck_change_case_type"),
        sa.CheckConstraint("status IN ('draft', 'active', 'completed', 'completed_with_exceptions', 'cancelled')", name="ck_change_case_status"),
    )
    op.create_table(
        "change_item",
        uuid_column("id", primary_key=True),
        sa.Column("case_id", UUID, sa.ForeignKey("change_case.id"), nullable=False),
        sa.Column("resource_id", UUID, sa.ForeignKey("resource.id"), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("assignee_person_id", UUID, sa.ForeignKey("person.id"), nullable=True),
        sa.Column("resource_person_id", UUID, sa.ForeignKey("resource_person.id"), nullable=True),
        sa.Column("account_binding_id", UUID, sa.ForeignKey("account_binding.id"), nullable=True),
        sa.Column("resource_relation_id", UUID, sa.ForeignKey("resource_relation.id"), nullable=True),
        sa.Column("from_person_id", UUID, sa.ForeignKey("person.id"), nullable=True),
        sa.Column("to_person_id", UUID, sa.ForeignKey("person.id"), nullable=True),
        sa.Column("new_contact_identity_id", UUID, sa.ForeignKey("contact_identity.id"), nullable=True),
        sa.Column("replacement_resource_id", UUID, sa.ForeignKey("resource.id"), nullable=True),
        sa.Column("expected_resource_version", sa.Integer(), nullable=True),
        sa.Column("expected_target_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_person_id", UUID, sa.ForeignKey("person.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_material_id", UUID, sa.ForeignKey("material.id"), nullable=True),
        sa.Column("non_secret_result", JSONB, nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint(
            "action IN ('change_owner', 'change_organization', 'change_visibility', 'remove_use', 'transfer_controller', 'change_binding', 'change_mailbox_address', 'change_management_relation', 'disable_resource', 'retire_resource', 'reactivate_resource')",
            name="ck_change_item_action",
        ),
        sa.CheckConstraint("status IN ('pending', 'in_progress', 'awaiting_confirmation', 'completed', 'cancelled')", name="ck_change_item_status"),
        sa.CheckConstraint(
            "(CASE WHEN resource_person_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN account_binding_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN resource_relation_id IS NULL THEN 0 ELSE 1 END) <= 1",
            name="ck_change_item_single_target",
        ),
    )
    op.create_table(
        "change_relation_detail",
        sa.Column("item_id", UUID, sa.ForeignKey("change_item.id"), primary_key=True),
        sa.Column("relation_id", UUID, sa.ForeignKey("resource_relation.id"), nullable=False),
        sa.Column("proposed_target_id", UUID, sa.ForeignKey("resource.id"), nullable=False),
    )
    op.create_table(
        "audit_event",
        uuid_column("id", primary_key=True),
        sa.Column("resource_id", UUID, sa.ForeignKey("resource.id"), nullable=True),
        sa.Column("change_item_id", UUID, sa.ForeignKey("change_item.id"), nullable=True),
        sa.Column("actor_person_id", UUID, sa.ForeignKey("person.id"), nullable=True),
        sa.Column("actor_kind", sa.String(length=16), server_default=sa.text("'system'"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        timestamp_column("occurred_at"),
        sa.Column("safe_before", JSONB, nullable=True),
        sa.Column("safe_after", JSONB, nullable=True),
        sa.Column("request_id", UUID, nullable=False),
    )

    op.create_index("ix_resource_type_code", "resource", ["type_code"])
    op.create_index("ix_resource_owning_department", "resource", ["owning_department_id"])
    op.create_index("ix_resource_updated_at", "resource", ["updated_at"])
    op.create_index("ix_resource_person_person_role", "resource_person", ["person_id", "role"])
    op.create_index("ix_resource_company_company_role", "resource_company", ["company_id", "role"])
    op.create_index("ix_resource_relation_source", "resource_relation", ["source_resource_id"])
    op.create_index("ix_resource_relation_target", "resource_relation", ["target_resource_id"])
    op.create_index(
        "uq_resource_person_current_owner",
        "resource_person",
        ["resource_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner' AND confirmation = 'confirmed' AND valid_to IS NULL"),
    )
    op.create_index(
        "uq_resource_company_current_owner",
        "resource_company",
        ["resource_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner' AND confirmation = 'confirmed' AND valid_to IS NULL"),
    )
    op.create_index(
        "uq_mailbox_current_primary_contact",
        "mailbox_contact_association",
        ["mailbox_account_id"],
        unique=True,
        postgresql_where=sa.text("role = 'primary' AND confirmation = 'confirmed' AND valid_to IS NULL"),
    )
    op.create_index(
        "uq_resource_relation_current_confirmed",
        "resource_relation",
        ["source_resource_id", "target_resource_id", "relation_type"],
        unique=True,
        postgresql_where=sa.text("confirmation = 'confirmed' AND valid_to IS NULL"),
    )
    op.create_index("ix_change_item_case_status", "change_item", ["case_id", "status"])
    op.create_index("ix_audit_event_resource_occurred", "audit_event", ["resource_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_event_resource_occurred", table_name="audit_event")
    op.drop_index("ix_change_item_case_status", table_name="change_item")
    op.drop_index("uq_resource_relation_current_confirmed", table_name="resource_relation")
    op.drop_index("uq_mailbox_current_primary_contact", table_name="mailbox_contact_association")
    op.drop_index("uq_resource_company_current_owner", table_name="resource_company")
    op.drop_index("uq_resource_person_current_owner", table_name="resource_person")
    op.drop_index("ix_resource_relation_target", table_name="resource_relation")
    op.drop_index("ix_resource_relation_source", table_name="resource_relation")
    op.drop_index("ix_resource_company_company_role", table_name="resource_company")
    op.drop_index("ix_resource_person_person_role", table_name="resource_person")
    op.drop_index("ix_resource_updated_at", table_name="resource")
    op.drop_index("ix_resource_owning_department", table_name="resource")
    op.drop_index("ix_resource_type_code", table_name="resource")

    op.drop_table("audit_event")
    op.drop_table("change_relation_detail")
    op.drop_table("change_item")
    op.drop_table("change_case")
    op.drop_table("material")
    op.drop_table("subscription_budget")
    op.drop_table("subscription_profile")
    op.drop_table("account_binding")
    op.drop_table("mailbox_contact_association")
    op.drop_table("contact_identity")
    op.drop_table("resource_relation")
    op.drop_table("resource_company")
    op.drop_table("resource_person")
    op.drop_table("account")
    op.drop_table("resource")
    op.drop_table("company")
    op.drop_table("person")
    op.drop_table("department")
