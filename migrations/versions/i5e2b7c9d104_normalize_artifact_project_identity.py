"""normalize artifact project identity

Revision ID: i5e2b7c9d104
Revises: h4d1a2b3c901
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i5e2b7c9d104"
down_revision: Union[str, Sequence[str], None] = "h4d1a2b3c901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.drop_index("ix_analysis_artifacts_project_code")
        batch.drop_column("avatar_color")
        batch.drop_column("avatar_initials")
        batch.drop_column("project_code")
        batch.drop_column("project_name")


def downgrade() -> None:
    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.add_column(sa.Column("project_name", sa.String(), nullable=True))
        batch.add_column(sa.Column("project_code", sa.String(), nullable=True))
        batch.add_column(sa.Column("avatar_initials", sa.String(), nullable=True))
        batch.add_column(sa.Column("avatar_color", sa.String(), nullable=True))

    connection = op.get_bind()
    projects = connection.execute(
        sa.text(
            """
            SELECT artifact.id AS artifact_id,
                   project.project_name,
                   project.project_code,
                   project.avatar_initials,
                   project.avatar_color
            FROM analysis_artifacts AS artifact
            JOIN projects AS project ON artifact.project_id = project.id
            """
        )
    ).mappings().all()
    update_artifact = sa.text(
        """
        UPDATE analysis_artifacts
        SET project_name = :project_name,
            project_code = :project_code,
            avatar_initials = :avatar_initials,
            avatar_color = :avatar_color
        WHERE id = :artifact_id
        """
    )
    for project in projects:
        connection.execute(update_artifact, dict(project))

    with op.batch_alter_table("analysis_artifacts") as batch:
        batch.alter_column("project_name", existing_type=sa.String(), nullable=False)
        batch.alter_column("project_code", existing_type=sa.String(), nullable=False)
        batch.alter_column("avatar_initials", existing_type=sa.String(), nullable=False)
        batch.alter_column("avatar_color", existing_type=sa.String(), nullable=False)
        batch.create_index("ix_analysis_artifacts_project_code", ["project_code"])
