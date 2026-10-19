"""Frozen append-only V3 Stage 2 migration."""
from alembic import op
import sqlalchemy as sa

revision = '0009_platform_jobs'
down_revision = '0008_subscription_ledger'
branch_labels = None
depends_on = None

DDL = ["CREATE TABLE platform_connection (\n\tid UUID NOT NULL, \n\tresource_id UUID NOT NULL, \n\tcredential_id UUID NOT NULL, \n\tcredential_version INTEGER NOT NULL, \n\tprovider VARCHAR(32) NOT NULL, \n\tlabel VARCHAR(200) NOT NULL, \n\tstatus VARCHAR(16) DEFAULT 'active' NOT NULL, \n\tinterval_seconds INTEGER DEFAULT 21600 NOT NULL, \n\tscheduled BOOLEAN DEFAULT false NOT NULL, \n\tnext_run_at TIMESTAMP WITH TIME ZONE, \n\tlast_attempt_at TIMESTAMP WITH TIME ZONE, \n\tlast_success_at TIMESTAMP WITH TIME ZONE, \n\tlast_error_code VARCHAR(64), \n\tcreated_by_person_id UUID NOT NULL, \n\tversion INTEGER DEFAULT 1 NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_connection_provider CHECK (provider = 'deepseek'), \n\tCONSTRAINT ck_connection_interval CHECK (interval_seconds >= 3600), \n\tFOREIGN KEY(resource_id) REFERENCES resource (id), \n\tFOREIGN KEY(credential_id) REFERENCES credential_ref (id), \n\tFOREIGN KEY(created_by_person_id) REFERENCES person (id)\n)", "CREATE TABLE sync_job (\n\tid UUID NOT NULL, \n\tresource_id UUID NOT NULL, \n\tconnection_id UUID NOT NULL, \n\tdedupe_key VARCHAR(100) NOT NULL, \n\tstatus VARCHAR(16) DEFAULT 'pending' NOT NULL, \n\tattempts INTEGER DEFAULT 0 NOT NULL, \n\tavailable_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tlease_until TIMESTAMP WITH TIME ZONE, \n\tlease_token UUID, \n\tlast_error_code VARCHAR(64), \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tfinished_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_sync_job_trigger UNIQUE (connection_id, dedupe_key), \n\tFOREIGN KEY(resource_id) REFERENCES resource (id), \n\tFOREIGN KEY(connection_id) REFERENCES platform_connection (id)\n)", 'CREATE TABLE metric_snapshot (\n\tid UUID NOT NULL, \n\tresource_id UUID NOT NULL, \n\tconnection_id UUID NOT NULL, \n\tjob_id UUID NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\ttotal_balance NUMERIC(24, 8) NOT NULL, \n\tgranted_balance NUMERIC(24, 8) NOT NULL, \n\ttopped_up_balance NUMERIC(24, 8) NOT NULL, \n\tis_available BOOLEAN NOT NULL, \n\tcollected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_snapshot_job_currency UNIQUE (job_id, currency), \n\tFOREIGN KEY(resource_id) REFERENCES resource (id), \n\tFOREIGN KEY(connection_id) REFERENCES platform_connection (id), \n\tFOREIGN KEY(job_id) REFERENCES sync_job (id)\n)']

def upgrade():
    for statement in DDL:
        op.execute(sa.text(statement))

def downgrade():
    raise RuntimeError("Use a verified database backup for rollback; destructive downgrade is not provided")
