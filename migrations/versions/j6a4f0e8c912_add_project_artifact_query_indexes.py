"""add project artifact query indexes

Revision ID: j6a4f0e8c912
Revises: i5e2b7c9d104
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op


revision: str = "j6a4f0e8c912"
down_revision: Union[str, Sequence[str], None] = "i5e2b7c9d104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These indexes match the route filters used for tenant scoping, archive visibility,
    # project/team access checks, latest-artifact rollups, and version history ordering.
    op.create_index(
        "ix_projects_tenant_archive_created",
        "projects",
        ["tenant_id", "is_deleted", "is_archived", "created_at"],
    )
    op.create_index(
        "ix_projects_tenant_name",
        "projects",
        ["tenant_id", "project_name"],
    )
    op.create_index(
        "ix_artifacts_project_active_created",
        "analysis_artifacts",
        ["project_id", "is_deleted", "is_archived", "created_at"],
    )
    op.create_index(
        "ix_artifacts_tenant_active_created",
        "analysis_artifacts",
        ["tenant_id", "is_deleted", "is_archived", "created_at"],
    )
    op.create_index(
        "ix_artifact_versions_artifact_created",
        "artifact_versions",
        ["artifact_id", "created_at"],
    )
    op.create_index(
        "ix_project_teams_team_project",
        "project_teams",
        ["team_id", "project_id"],
    )
    op.create_index(
        "ix_team_memberships_user_team",
        "team_memberships",
        ["user_id", "team_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_team_memberships_user_team", table_name="team_memberships")
    op.drop_index("ix_project_teams_team_project", table_name="project_teams")
    op.drop_index("ix_artifact_versions_artifact_created", table_name="artifact_versions")
    op.drop_index("ix_artifacts_tenant_active_created", table_name="analysis_artifacts")
    op.drop_index("ix_artifacts_project_active_created", table_name="analysis_artifacts")
    op.drop_index("ix_projects_tenant_name", table_name="projects")
    op.drop_index("ix_projects_tenant_archive_created", table_name="projects")
