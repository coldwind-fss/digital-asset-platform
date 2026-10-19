from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "0001_instance"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    config = context.get_context().config
    instance_id = config.attributes.get("instance_id")
    environment = config.attributes.get("environment")
    if not instance_id or not environment:
        raise RuntimeError("Digital Asset Platform migration target marker is missing")

    op.create_table(
        "instance_metadata",
        sa.Column("singleton_key", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column("schema_family", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("singleton_key = 1", name="ck_instance_metadata_singleton"),
        sa.PrimaryKeyConstraint("singleton_key"),
        sa.UniqueConstraint("instance_id", name="uq_instance_metadata_instance_id"),
    )
    table = sa.table(
        "instance_metadata",
        sa.column("singleton_key", sa.Integer()),
        sa.column("instance_id", sa.String()),
        sa.column("environment", sa.String()),
        sa.column("schema_family", sa.String()),
    )
    op.bulk_insert(
        table,
        [
            {
                "singleton_key": 1,
                "instance_id": instance_id,
                "environment": environment,
                "schema_family": "digital_asset_platform_resource",
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("instance_metadata")
