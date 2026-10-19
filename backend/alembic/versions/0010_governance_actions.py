"""Frozen append-only V3 Stage 2 migration."""
from alembic import op
import sqlalchemy as sa

revision = '0010_governance_actions'
down_revision = '0009_platform_jobs'
branch_labels = None
depends_on = None

DDL = ["ALTER TABLE change_item ADD COLUMN proposal_json JSONB, ADD COLUMN execution_history JSONB NOT NULL DEFAULT '[]'::jsonb, ADD COLUMN executed_by_person_id UUID REFERENCES person(id), ADD COLUMN cancellation_requested_by UUID REFERENCES person(id)", 'ALTER TABLE change_item DROP CONSTRAINT ck_change_item_action', "ALTER TABLE change_item ADD CONSTRAINT ck_change_item_action CHECK (action IN ('change_owner', 'change_organization', 'change_visibility', 'grant_use', 'remove_use', 'transfer_controller', 'change_binding', 'change_mailbox_address', 'change_management_relation', 'disable_resource', 'retire_resource', 'reactivate_resource', 'rotate_credential', 'revoke_credential_grant', 'revoke_credential', 'replace_key'))", 'ALTER TABLE change_item DROP CONSTRAINT ck_change_item_status', "ALTER TABLE change_item ADD CONSTRAINT ck_change_item_status CHECK (status IN ('pending', 'in_progress', 'awaiting_confirmation', 'completed', 'cancelled', 'failed', 'cancellation_requested'))"]

def upgrade():
    for statement in DDL:
        op.execute(sa.text(statement))

def downgrade():
    raise RuntimeError("Use a verified database backup for rollback; destructive downgrade is not provided")
