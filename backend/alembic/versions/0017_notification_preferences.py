"""Personal display preference, independent of reminder business state."""
from alembic import op
import sqlalchemy as sa
revision='0017_notification_preferences'
down_revision='0016_import_mapping'
branch_labels=None
depends_on=None
def upgrade():op.create_table('notification_preference',sa.Column('person_id',sa.Uuid(),sa.ForeignKey('person.id'),primary_key=True),sa.Column('show_due',sa.Boolean(),nullable=False,server_default=sa.text('true')),sa.Column('version',sa.Integer(),nullable=False,server_default=sa.text('1')))
def downgrade():raise RuntimeError('Restore a verified backup for rollback')
