"""Frozen append-only V3 Stage 2 migration."""
from alembic import op
import sqlalchemy as sa

revision = '0007_credential_operations'
down_revision = '0006_core_facts'
branch_labels = None
depends_on = None

DDL = ["ALTER TABLE credential_stage ADD COLUMN resource_id UUID REFERENCES resource(id), ADD COLUMN purpose VARCHAR(16) NOT NULL DEFAULT 'attach'", 'ALTER TABLE credential_ref DROP CONSTRAINT ck_credential_ref_status', "ALTER TABLE credential_ref ADD CONSTRAINT ck_credential_ref_status CHECK (status IN ('not_saved', 'pending', 'saved', 'failed', 'superseded', 'revoked'))", 'ALTER TABLE credential_ref DROP CONSTRAINT ck_credential_ref_material_state', "ALTER TABLE credential_ref ADD CONSTRAINT ck_credential_ref_material_state CHECK ((status IN ('saved','superseded','revoked') AND ciphertext IS NOT NULL AND nonce IS NOT NULL AND key_version IS NOT NULL) OR (status NOT IN ('saved','superseded','revoked') AND ciphertext IS NULL AND nonce IS NULL))", "CREATE TABLE credential_operation (\n\tid UUID NOT NULL, \n\tresource_id UUID NOT NULL, \n\tcredential_id UUID NOT NULL, \n\tstage_id UUID, \n\tgrant_id UUID, \n\taction VARCHAR(32) NOT NULL, \n\texpected_credential_version INTEGER NOT NULL, \n\tcreated_by_person_id UUID NOT NULL, \n\tstatus VARCHAR(16) DEFAULT 'prepared' NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tresult_credential_id UUID, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_credential_operation_status CHECK (status IN ('prepared','applied','cancelled')), \n\tFOREIGN KEY(resource_id) REFERENCES resource (id), \n\tFOREIGN KEY(credential_id) REFERENCES credential_ref (id), \n\tFOREIGN KEY(stage_id) REFERENCES credential_stage (id), \n\tFOREIGN KEY(grant_id) REFERENCES credential_grant (id), \n\tFOREIGN KEY(created_by_person_id) REFERENCES person (id), \n\tFOREIGN KEY(result_credential_id) REFERENCES credential_ref (id)\n)"]

def upgrade():
    for statement in DDL:
        op.execute(sa.text(statement))

def downgrade():
    raise RuntimeError("Use a verified database backup for rollback; destructive downgrade is not provided")
