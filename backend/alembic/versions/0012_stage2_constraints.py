"""Additional frozen constraints and prepared secret material."""
from alembic import op
import sqlalchemy as sa
revision="0012_stage2_constraints"
down_revision="0011_imports_files"
branch_labels=None
depends_on=None


def upgrade():
    op.execute(sa.text("ALTER TABLE credential_operation ADD COLUMN ciphertext BYTEA, ADD COLUMN nonce BYTEA, ADD COLUMN key_version VARCHAR(64)"))
    op.execute(sa.text("CREATE UNIQUE INDEX uq_resource_external_instance ON resource(type_code,platform_id,(attributes->>'external_instance_id')) WHERE platform_id IS NOT NULL AND type_code IN ('api_service','cloud_resource','business_space') AND attributes->>'external_instance_id' IS NOT NULL AND attributes->>'external_instance_id' <> '' AND archived_at IS NULL"))


def downgrade():
    raise RuntimeError("Restore a verified backup for rollback")
