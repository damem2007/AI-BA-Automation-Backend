"""add first-class projects

Revision ID: h4d1a2b3c901
Revises: g3c8e012f864
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h4d1a2b3c901"
down_revision: Union[str, Sequence[str], None] = "g3c8e012f864"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(), nullable=False),
        sa.Column("project_code", sa.String(), nullable=False),
        sa.Column("avatar_initials", sa.String(), nullable=False),
        sa.Column("avatar_color", sa.String(), nullable=False),
        sa.Column("project_type", sa.String(), server_default="internal", nullable=False),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("domain", sa.String(), nullable=True),
        sa.Column("initiative_type", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.String(), server_default="local", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "project_code", name="uq_project_tenant_project_code"),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])
    op.create_index("ix_projects_project_code", "projects", ["project_code"])
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index("ix_projects_is_archived", "projects", ["is_archived"])

    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch.create_index("ix_analysis_artifacts_project_id", ["project_id"])
        batch.create_foreign_key("fk_analysis_artifacts_project_id_projects", "projects", ["project_id"], ["id"])
        batch.drop_constraint("uq_artifact_tenant_project_code", type_="unique")

    with op.batch_alter_table("project_teams") as batch:
        batch.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch.create_index("ix_project_teams_project_id", ["project_id"])
        batch.create_foreign_key("fk_project_teams_project_id_projects", "projects", ["project_id"], ["id"])
        batch.drop_constraint("uq_project_team", type_="unique")
        batch.alter_column("artifact_id", existing_type=sa.Integer(), nullable=True)

    connection = op.get_bind()
    artifacts = connection.execute(
        sa.text(
            """
            SELECT id, project_name, project_code, avatar_initials, avatar_color,
                   project_type, company_name, industry, domain, country,
                   owner_user_id, tenant_id, is_deleted, is_archived, archived_at,
                   archived_by, created_at
            FROM analysis_artifacts
            ORDER BY id
            """
        )
    ).mappings().all()
    insert_project = sa.text(
        """
        INSERT INTO projects (
            project_name, project_code, avatar_initials, avatar_color,
            project_type, company_name, industry, domain, country,
            owner_user_id, tenant_id, is_deleted, is_archived, archived_at,
            archived_by, created_at, updated_at
        )
        VALUES (
            :project_name, :project_code, :avatar_initials, :avatar_color,
            :project_type, :company_name, :industry, :domain, :country,
            :owner_user_id, :tenant_id, :is_deleted, :is_archived, :archived_at,
            :archived_by, :created_at, :created_at
        )
        """
    )
    for artifact in artifacts:
        connection.execute(
            insert_project,
            {
                "project_name": artifact["project_name"],
                "project_code": artifact["project_code"],
                "avatar_initials": artifact["avatar_initials"],
                "avatar_color": artifact["avatar_color"],
                "project_type": artifact["project_type"] or "internal",
                "company_name": artifact["company_name"],
                "industry": artifact["industry"],
                "domain": artifact["domain"],
                "country": artifact["country"],
                "owner_user_id": artifact["owner_user_id"],
                "tenant_id": artifact["tenant_id"] or "local",
                "is_deleted": artifact["is_deleted"] or False,
                "is_archived": artifact["is_archived"] or False,
                "archived_at": artifact["archived_at"],
                "archived_by": artifact["archived_by"],
                "created_at": artifact["created_at"],
            },
        )
        project_id = connection.execute(
            sa.text(
                """
                SELECT id FROM projects
                WHERE tenant_id = :tenant_id AND project_code = :project_code
                """
            ),
            {
                "tenant_id": artifact["tenant_id"] or "local",
                "project_code": artifact["project_code"],
            },
        ).scalar()
        connection.execute(
            sa.text("UPDATE analysis_artifacts SET project_id = :project_id WHERE id = :artifact_id"),
            {"project_id": project_id, "artifact_id": artifact["id"]},
        )
        connection.execute(
            sa.text("UPDATE project_teams SET project_id = :project_id WHERE artifact_id = :artifact_id"),
            {"project_id": project_id, "artifact_id": artifact["id"]},
        )

    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.alter_column("project_id", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("project_teams") as batch:
        batch.alter_column("project_id", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint("uq_project_team", ["project_id", "team_id"])


def downgrade() -> None:
    with op.batch_alter_table("project_teams") as batch:
        batch.drop_constraint("uq_project_team", type_="unique")
        batch.drop_constraint("fk_project_teams_project_id_projects", type_="foreignkey")
        batch.drop_index("ix_project_teams_project_id")
        batch.drop_column("project_id")

    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.drop_constraint("fk_analysis_artifacts_project_id_projects", type_="foreignkey")
        batch.drop_index("ix_analysis_artifacts_project_id")
        batch.drop_column("project_id")
        batch.create_unique_constraint("uq_artifact_tenant_project_code", ["tenant_id", "project_code"])

    op.drop_index("ix_projects_is_archived", table_name="projects")
    op.drop_index("ix_projects_tenant_id", table_name="projects")
    op.drop_index("ix_projects_project_code", table_name="projects")
    op.drop_index("ix_projects_owner_user_id", table_name="projects")
    op.drop_index("ix_projects_id", table_name="projects")
    op.drop_table("projects")
