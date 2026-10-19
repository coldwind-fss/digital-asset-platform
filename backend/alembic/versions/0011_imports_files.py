"""Frozen append-only V3 Stage 2 migration."""
from alembic import op
import sqlalchemy as sa

revision = '0011_imports_files'
down_revision = '0010_governance_actions'
branch_labels = None
depends_on = None

DDL = ["CREATE TABLE import_batch (\n\tid UUID NOT NULL, \n\tcreated_by_person_id UUID NOT NULL, \n\ttype_code VARCHAR(32) NOT NULL, \n\tlabel VARCHAR(200) NOT NULL, \n\tcontent_digest VARCHAR(64) NOT NULL, \n\trows JSONB NOT NULL, \n\tresults JSONB NOT NULL, \n\tstatus VARCHAR(16) DEFAULT 'preview' NOT NULL, \n\tversion INTEGER DEFAULT 1 NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcommitted_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(created_by_person_id) REFERENCES person (id)\n)", "CREATE TABLE private_file (\n\tid UUID NOT NULL, \n\tresource_id UUID NOT NULL, \n\tfilename VARCHAR(200) NOT NULL, \n\tstorage_key VARCHAR(100) NOT NULL, \n\tmedia_type VARCHAR(100) NOT NULL, \n\tsize_bytes INTEGER NOT NULL, \n\tsha256 VARCHAR(64) NOT NULL, \n\tstatus VARCHAR(16) DEFAULT 'available' NOT NULL, \n\tclassification VARCHAR(16) DEFAULT 'normal' NOT NULL, \n\tcheck_policy VARCHAR(64) NOT NULL, \n\treplaces_file_id UUID, \n\tcreated_by_person_id UUID NOT NULL, \n\tversion INTEGER DEFAULT 1 NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tended_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(resource_id) REFERENCES resource (id), \n\tUNIQUE (storage_key), \n\tFOREIGN KEY(replaces_file_id) REFERENCES private_file (id), \n\tFOREIGN KEY(created_by_person_id) REFERENCES person (id)\n)"]

def upgrade():
    for statement in DDL:
        op.execute(sa.text(statement))

def downgrade():
    raise RuntimeError("Use a verified database backup for rollback; destructive downgrade is not provided")
