"""Add application-managed encrypted credential references and grants."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_credential_storage"
down_revision = "0002_core_schema"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)


def uuid_column(name: str, *, primary_key: bool = False) -> sa.Column:
    return sa.Column(name, UUID, nullable=False, primary_key=primary_key)


def timestamp_column(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "credential_ref",
        uuid_column("id", primary_key=True),
        sa.Column("resource_id", UUID, sa.ForeignKey("resource.id"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'not_saved'"), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("nonce", sa.LargeBinary(), nullable=True),
        sa.Column("key_version", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint("kind IN ('password', 'api_key', 'certificate_pin', 'other')", name="ck_credential_ref_kind"),
        sa.CheckConstraint("status IN ('not_saved', 'pending', 'saved', 'failed')", name="ck_credential_ref_status"),
        sa.CheckConstraint(
            "(status = 'saved' AND ciphertext IS NOT NULL AND nonce IS NOT NULL AND key_version IS NOT NULL) OR "
            "(status <> 'saved' AND ciphertext IS NULL AND nonce IS NULL)",
            name="ck_credential_ref_material_state",
        ),
    )
    op.create_table(
        "credential_grant",
        uuid_column("id", primary_key=True),
        sa.Column("credential_id", UUID, sa.ForeignKey("credential_ref.id"), nullable=False),
        sa.Column("person_id", UUID, sa.ForeignKey("person.id"), nullable=False),
        sa.Column("capability", sa.String(length=16), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.CheckConstraint("capability IN ('view', 'rotate')", name="ck_credential_grant_capability"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_credential_grant_valid_range"),
    )
    op.create_table(
        "credential_stage",
        uuid_column("id", primary_key=True),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        timestamp_column("created_at"),
        sa.CheckConstraint("kind IN ('password', 'api_key', 'certificate_pin', 'other')", name="ck_credential_stage_kind"),
        sa.CheckConstraint("consumed_at IS NULL OR consumed_at >= created_at", name="ck_credential_stage_consumed_range"),
    )
    op.create_index("ix_credential_ref_resource", "credential_ref", ["resource_id"])
    op.create_index("ix_credential_grant_credential", "credential_grant", ["credential_id"])
    op.create_index("ix_credential_grant_person", "credential_grant", ["person_id"])


def downgrade() -> None:
    op.drop_index("ix_credential_grant_person", table_name="credential_grant")
    op.drop_index("ix_credential_grant_credential", table_name="credential_grant")
    op.drop_index("ix_credential_ref_resource", table_name="credential_ref")
    op.drop_table("credential_stage")
    op.drop_table("credential_grant")
    op.drop_table("credential_ref")
