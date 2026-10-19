"""Retain non-secret CSV field mapping with batch provenance."""
from alembic import op
import sqlalchemy as sa
revision='0016_import_mapping'
down_revision='0015_directory_person_version'
branch_labels=None
depends_on=None
def upgrade():op.execute(sa.text("ALTER TABLE import_batch ADD COLUMN mapping JSONB NOT NULL DEFAULT '{}'::jsonb"))
def downgrade():raise RuntimeError('Restore a verified backup for rollback')
