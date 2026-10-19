"""Identity and directory foundation. Frozen append-only DDL."""
from alembic import op
import sqlalchemy as sa

revision = "0005_identity_foundation"
down_revision = "0004_material_version"
branch_labels = None
depends_on = None


def uid(name="id", primary=False, reference=None, nullable=False):
    args = [sa.Uuid()]
    if reference:
        args.append(sa.ForeignKey(reference))
    return sa.Column(name, *args, primary_key=primary, nullable=nullable)


def timestamp(name):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))


def upgrade() -> None:
    op.create_table("platform",
        uid(primary=True), sa.Column("name",sa.String(200),nullable=False),
        sa.Column("website",sa.String(2000)), sa.Column("status",sa.String(16),nullable=False,server_default="unknown"),
        sa.Column("version",sa.Integer(),nullable=False,server_default="1"), timestamp("created_at"),timestamp("updated_at"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'unknown')",name="ck_platform_status"))
    op.create_table("auth_account",
        uid(primary=True),uid("person_id",reference="person.id"),
        sa.Column("username",sa.String(64),nullable=False),sa.Column("password_hash",sa.String(256)),
        sa.Column("role",sa.String(32),nullable=False,server_default="member"),
        sa.Column("status",sa.String(16),nullable=False,server_default="pending"),
        sa.Column("must_change_password",sa.Boolean(),nullable=False,server_default=sa.text("false")),
        sa.Column("version",sa.Integer(),nullable=False,server_default="1"),timestamp("created_at"),timestamp("updated_at"),
        sa.UniqueConstraint("username"),sa.UniqueConstraint("person_id"),
        sa.CheckConstraint("role IN ('admin', 'resource_manager', 'member')",name="ck_auth_account_role"),
        sa.CheckConstraint("status IN ('pending', 'active', 'inactive')",name="ck_auth_account_status"),
        sa.CheckConstraint("username = lower(username)",name="ck_auth_account_username_lower"),
        sa.CheckConstraint("status <> 'active' OR password_hash IS NOT NULL",name="ck_auth_account_active_password"))
    op.create_table("auth_session",
        uid(primary=True),uid("account_id",reference="auth_account.id"),
        sa.Column("token_hash",sa.LargeBinary(),nullable=False,unique=True),
        sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("last_seen_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("authenticated_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("revoked_at",sa.DateTime(timezone=True)),timestamp("created_at"))
    op.create_index("ix_auth_session_account_id","auth_session",["account_id"])
    op.create_table("auth_scope",
        uid(primary=True),uid("account_id",reference="auth_account.id"),sa.Column("kind",sa.String(16),nullable=False),
        uid("target_id"),sa.Column("permission",sa.String(16),nullable=False),
        sa.CheckConstraint("kind IN ('department', 'resource')",name="ck_auth_scope_kind"),
        sa.CheckConstraint("permission IN ('read', 'manage')",name="ck_auth_scope_permission"),
        sa.UniqueConstraint("account_id","kind","target_id",name="uq_auth_scope_target"))
    op.create_index("ix_auth_scope_account_id","auth_scope",["account_id"])
    op.create_table("auth_action_token",
        uid(primary=True),uid("account_id",reference="auth_account.id"),
        sa.Column("token_hash",sa.LargeBinary(),nullable=False,unique=True),
        sa.Column("purpose",sa.String(16),nullable=False),
        sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("used_at",sa.DateTime(timezone=True)),timestamp("created_at"),
        sa.CheckConstraint("purpose IN ('activate', 'recover')",name="ck_auth_action_token_purpose"))
    op.create_index("ix_auth_action_token_account_id","auth_action_token",["account_id"])
    op.create_table("auth_throttle",
        sa.Column("key",sa.String(64),primary_key=True),sa.Column("failures",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("window_started_at",sa.DateTime(timezone=True),nullable=False),sa.Column("blocked_until",sa.DateTime(timezone=True)))
    op.add_column("department",sa.Column("version",sa.Integer(),nullable=False,server_default="1"))
    op.add_column("resource",uid("created_by_person_id",reference="person.id",nullable=True))
    op.add_column("resource",uid("platform_id",reference="platform.id",nullable=True))
    op.add_column("credential_stage",uid("created_by_person_id",reference="person.id",nullable=True))
    op.add_column("change_case",uid("created_by_person_id",reference="person.id",nullable=True))
    op.create_index("ix_resource_created_by","resource",["created_by_person_id"])
    op.create_index("ix_resource_platform","resource",["platform_id"])


def downgrade() -> None:
    op.drop_index("ix_resource_platform",table_name="resource")
    op.drop_index("ix_resource_created_by",table_name="resource")
    op.drop_column("change_case","created_by_person_id")
    op.drop_column("credential_stage","created_by_person_id")
    op.drop_column("resource","platform_id")
    op.drop_column("resource","created_by_person_id")
    op.drop_column("department","version")
    for table in ("auth_throttle","auth_action_token","auth_scope","auth_session","auth_account","platform"):
        op.drop_table(table)
