"""add identity teams and archives

Revision ID: a7c1e9b4f210
Revises: 41be02a60b56
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c1e9b4f210"
down_revision: Union[str, Sequence[str], None] = "41be02a60b56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="roles_name_key"),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)
    op.create_index("ix_roles_is_archived", "roles", ["is_archived"])

    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("external_subject", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="local"),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("external_subject", name="users_external_subject_key"),
        sa.UniqueConstraint("username", name="users_username_key"),
        sa.UniqueConstraint("email", name="users_email_key"),
    )
    op.create_index("ix_users_external_subject", "users", ["external_subject"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_index("ix_users_is_archived", "users", ["is_archived"])

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("owner_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="teams_slug_key"),
    )
    op.create_index("ix_teams_slug", "teams", ["slug"], unique=True)
    op.create_index("ix_teams_owner_user_id", "teams", ["owner_user_id"])
    op.create_index("ix_teams_is_archived", "teams", ["is_archived"])

    op.create_table(
        "team_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("membership_role", sa.String(), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_membership"),
    )
    op.create_index("ix_team_memberships_team_id", "team_memberships", ["team_id"])
    op.create_index("ix_team_memberships_user_id", "team_memberships", ["user_id"])

    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.add_column(sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("archived_by", sa.String(), nullable=True))
        batch.add_column(sa.Column("owner_user_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("team_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_analysis_artifacts_owner_user", "users", ["owner_user_id"], ["id"])
        batch.create_foreign_key("fk_analysis_artifacts_team", "teams", ["team_id"], ["id"])
        batch.create_index("ix_analysis_artifacts_is_archived", ["is_archived"])
        batch.create_index("ix_analysis_artifacts_owner_user_id", ["owner_user_id"])
        batch.create_index("ix_analysis_artifacts_team_id", ["team_id"])


def downgrade() -> None:
    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.drop_index("ix_analysis_artifacts_team_id")
        batch.drop_index("ix_analysis_artifacts_owner_user_id")
        batch.drop_index("ix_analysis_artifacts_is_archived")
        batch.drop_constraint("fk_analysis_artifacts_team", type_="foreignkey")
        batch.drop_constraint("fk_analysis_artifacts_owner_user", type_="foreignkey")
        batch.drop_column("team_id")
        batch.drop_column("owner_user_id")
        batch.drop_column("archived_by")
        batch.drop_column("archived_at")
        batch.drop_column("is_archived")
    op.drop_table("team_memberships")
    op.drop_table("teams")
    op.drop_table("users")
    op.drop_table("roles")
