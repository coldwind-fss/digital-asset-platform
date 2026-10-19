"""Add optimistic versioning to non-secret materials."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_material_version"
down_revision = "0003_credential_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "material",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("material", "version")
