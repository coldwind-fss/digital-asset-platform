"""Version non-login business directory people independently of auth accounts."""
from alembic import op
import sqlalchemy as sa
revision='0015_directory_person_version'
down_revision='0014_worker_heartbeat'
branch_labels=None
depends_on=None
def upgrade():op.add_column('person',sa.Column('version',sa.Integer(),nullable=False,server_default=sa.text('1')))
def downgrade():raise RuntimeError('Restore a verified backup for rollback')
