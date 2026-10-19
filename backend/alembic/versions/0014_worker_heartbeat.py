"""Persist local worker liveness without exposing process secrets."""
from alembic import op
import sqlalchemy as sa
revision = "0014_worker_heartbeat"
down_revision = "0013_ledger_due_constraints"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("worker_heartbeat", sa.Column("id", sa.String(64), primary_key=True), sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False))

def downgrade():
    raise RuntimeError("Restore a verified backup for rollback")
