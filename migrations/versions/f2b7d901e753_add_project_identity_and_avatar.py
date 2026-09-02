"""add project identity and avatar

Revision ID: f2b7d901e753
Revises: e1a6c8f0d642
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.services.project_generator import generate_artifact_avatar, generate_project_code


revision: str = "f2b7d901e753"
down_revision: Union[str, Sequence[str], None] = "e1a6c8f0d642"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analysis_artifacts", sa.Column("project_code", sa.String(), nullable=True))
    op.add_column("analysis_artifacts", sa.Column("avatar_initials", sa.String(), nullable=True))
    op.add_column("analysis_artifacts", sa.Column("avatar_color", sa.String(), nullable=True))

    connection = op.get_bind()
    artifacts = connection.execute(
        sa.text(
            """
            SELECT id, tenant_id, project_name
            FROM analysis_artifacts
            ORDER BY tenant_id, id
            """
        )
    ).mappings().all()
    used_codes: set[tuple[str, str]] = set()
    update_artifact = sa.text(
        """
        UPDATE analysis_artifacts
        SET project_code = :project_code,
            avatar_initials = :avatar_initials,
            avatar_color = :avatar_color
        WHERE id = :artifact_id
        """
    )
    for artifact in artifacts:
        tenant_id = artifact["tenant_id"] or "local"
        project_name = artifact["project_name"] or "Project"
        project_code = generate_project_code(project_name)
        while (tenant_id, project_code) in used_codes:
            project_code = generate_project_code(project_name)
        used_codes.add((tenant_id, project_code))
        avatar_color, avatar_initials = generate_artifact_avatar(project_name)
        connection.execute(
            update_artifact,
            {
                "artifact_id": artifact["id"],
                "project_code": project_code,
                "avatar_initials": avatar_initials,
                "avatar_color": avatar_color,
            },
        )

    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.alter_column("project_code", existing_type=sa.String(), nullable=False)
        batch.alter_column("avatar_initials", existing_type=sa.String(), nullable=False)
        batch.alter_column("avatar_color", existing_type=sa.String(), nullable=False)
        batch.create_index("ix_analysis_artifacts_project_code", ["project_code"])
        batch.create_unique_constraint("uq_artifact_tenant_project_code", ["tenant_id", "project_code"])


def downgrade() -> None:
    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.drop_constraint("uq_artifact_tenant_project_code", type_="unique")
        batch.drop_index("ix_analysis_artifacts_project_code")
        batch.drop_column("avatar_color")
        batch.drop_column("avatar_initials")
        batch.drop_column("project_code")
