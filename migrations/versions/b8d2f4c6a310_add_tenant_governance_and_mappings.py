"""add tenant governance and mappings

Revision ID: b8d2f4c6a310
Revises: a7c1e9b4f210
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8d2f4c6a310"
down_revision: Union[str, Sequence[str], None] = "a7c1e9b4f210"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("roles", sa.Column("tenant_id", sa.String(), nullable=True))
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])

    op.add_column("users", sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("auth_source", sa.String(), nullable=False, server_default="local"))
    op.add_column("users", sa.Column("status", sa.String(), nullable=False, server_default="active"))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("onboarding_status", sa.String(), nullable=False, server_default="pending"))
    op.create_index("ix_users_status", "users", ["status"])

    op.add_column("teams", sa.Column("tenant_id", sa.String(), nullable=False, server_default="local"))
    op.create_index("ix_teams_tenant_id", "teams", ["tenant_id"])
    op.add_column("analysis_artifacts", sa.Column("tenant_id", sa.String(), nullable=False, server_default="local"))
    op.create_index("ix_analysis_artifacts_tenant_id", "analysis_artifacts", ["tenant_id"])

    op.create_table(
        "project_teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("artifact_id", sa.Integer(), sa.ForeignKey("analysis_artifacts.id"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("assigned_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("artifact_id", "team_id", name="uq_project_team"),
    )
    op.create_index("ix_project_teams_artifact_id", "project_teams", ["artifact_id"])
    op.create_index("ix_project_teams_team_id", "project_teams", ["team_id"])

    op.create_table(
        "tenant_settings",
        sa.Column("tenant_id", sa.String(), primary_key=True),
        sa.Column("allow_multiple_teams_per_project", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("password_min_length", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("password_require_uppercase", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("password_require_lowercase", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("password_require_number", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("password_require_special", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("password_expiration_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "identity_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("provider_type", sa.String(), nullable=False, server_default="oidc"),
        sa.Column("issuer", sa.String(), nullable=False, unique=True),
        sa.Column("audience", sa.String(), nullable=False),
        sa.Column("jwks_url", sa.String(), nullable=False),
        sa.Column("required_scopes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("users_endpoint", sa.String(), nullable=True),
        sa.Column("token_env_key", sa.String(), nullable=True),
        sa.Column("icon_key", sa.String(), nullable=False, server_default="key"),
        sa.Column("default_role", sa.String(), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_identity_providers_tenant_id", "identity_providers", ["tenant_id"])
    op.create_index("ix_identity_providers_is_active", "identity_providers", ["is_active"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)

    op.execute("UPDATE users SET is_global = true, onboarding_status = 'complete' WHERE id = 'user-root-local'")
    op.execute("UPDATE users SET password_changed_at = NOW() WHERE password_hash IS NOT NULL AND password_changed_at IS NULL")
    op.execute("INSERT INTO tenant_settings (tenant_id) VALUES ('local') ON CONFLICT (tenant_id) DO NOTHING")
    op.execute(
        """
        INSERT INTO project_teams (artifact_id, team_id, assigned_by)
        SELECT id, team_id, COALESCE(owner_user_id, 'user-root-local')
        FROM analysis_artifacts
        WHERE team_id IS NOT NULL
        ON CONFLICT (artifact_id, team_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_table("identity_providers")
    op.drop_table("tenant_settings")
    op.drop_table("project_teams")
    op.drop_index("ix_analysis_artifacts_tenant_id", table_name="analysis_artifacts")
    op.drop_column("analysis_artifacts", "tenant_id")
    op.drop_index("ix_teams_tenant_id", table_name="teams")
    op.drop_column("teams", "tenant_id")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_column("users", "onboarding_status")
    op.drop_column("users", "password_expires_at")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "status")
    op.drop_column("users", "auth_source")
    op.drop_column("users", "is_global")
    op.drop_index("ix_roles_tenant_id", table_name="roles")
    op.drop_column("roles", "tenant_id")
