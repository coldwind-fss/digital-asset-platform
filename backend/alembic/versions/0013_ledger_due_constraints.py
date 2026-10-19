"""Explicit assigned seats, correction links, and non-financial domain expiry."""
from alembic import op
import sqlalchemy as sa
revision="0013_ledger_due_constraints"
down_revision="0012_stage2_constraints"
branch_labels=None
depends_on=None


def upgrade():
    for statement in [
        "ALTER TABLE subscription_ledger ADD COLUMN seats_assigned INTEGER, ADD CONSTRAINT ck_assigned_seats CHECK (seats_assigned IS NULL OR (seats_assigned >= 0 AND (seats_total IS NULL OR seats_assigned <= seats_total)))",
        "ALTER TABLE expense_entry ADD COLUMN corrects_entry_id UUID REFERENCES expense_entry(id)",
        "ALTER TABLE reminder_item ALTER COLUMN period_id DROP NOT NULL, ADD COLUMN due_on DATE",
        "UPDATE reminder_item SET due_on=subscription_period.ends_on FROM subscription_period WHERE reminder_item.period_id=subscription_period.id",
        "ALTER TABLE reminder_item ALTER COLUMN due_on SET NOT NULL",
        "CREATE UNIQUE INDEX uq_resource_expiry_window ON reminder_item(resource_id,due_on,window_days) WHERE period_id IS NULL",
    ]:op.execute(sa.text(statement))


def downgrade():raise RuntimeError("Restore a verified backup for rollback")
