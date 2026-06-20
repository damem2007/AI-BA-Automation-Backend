"""add tenant lineage and per-team project policy

Revision ID: c9e4a6d8b420
Revises: b8d2f4c6a310
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9e4a6d8b420"
down_revision: Union[str, Sequence[str], None] = "b8d2f4c6a310"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenants_status", "tenants", ["status"])
    op.execute("INSERT INTO tenants (id, name) VALUES ('local', 'Local Organization')")

    op.add_column("teams", sa.Column("allow_multiple_projects", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(
        """
        UPDATE teams SET allow_multiple_projects = true
        WHERE id IN (
            SELECT team_id FROM project_teams GROUP BY team_id HAVING COUNT(DISTINCT artifact_id) > 1
        )
        """
    )

    for table in ("artifact_versions", "team_memberships", "project_teams", "password_reset_tokens"):
        op.add_column(table, sa.Column("tenant_id", sa.String(), nullable=False, server_default="local"))
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])

    op.execute(
        """
        UPDATE artifact_versions AS version SET tenant_id = artifact.tenant_id
        FROM analysis_artifacts AS artifact WHERE artifact.id = version.artifact_id
        """
    )
    op.execute(
        """
        UPDATE team_memberships AS membership SET tenant_id = team.tenant_id
        FROM teams AS team WHERE team.id = membership.team_id
        """
    )
    op.execute(
        """
        UPDATE project_teams AS mapping SET tenant_id = artifact.tenant_id
        FROM analysis_artifacts AS artifact WHERE artifact.id = mapping.artifact_id
        """
    )
    op.execute(
        """
        UPDATE password_reset_tokens AS token SET tenant_id = app_user.tenant_id
        FROM users AS app_user WHERE app_user.id = token.user_id
        """
    )
    op.drop_column("tenant_settings", "allow_multiple_teams_per_project")


def downgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column("allow_multiple_teams_per_project", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for table in ("password_reset_tokens", "project_teams", "team_memberships", "artifact_versions"):
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")
    op.drop_column("teams", "allow_multiple_projects")
    op.drop_index("ix_tenants_status", table_name="tenants")
    op.drop_table("tenants")
