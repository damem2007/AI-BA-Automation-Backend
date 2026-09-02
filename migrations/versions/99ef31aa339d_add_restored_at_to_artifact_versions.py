"""add restored_at to artifact versions

Revision ID: 99ef31aa339d
Revises: 
Create Date: 2026-05-26 15:31:19.138382

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99ef31aa339d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "analysis_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("analysis_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_artifacts_id"), "analysis_artifacts", ["id"], unique=False)

    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("analysis_json", sa.JSON(), nullable=False),
        sa.Column("version_type", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_artifact_versions_id"), "artifact_versions", ["id"], unique=False)
    op.create_index(op.f("ix_artifact_versions_artifact_id"), "artifact_versions", ["artifact_id"], unique=False)
    op.create_index(op.f("ix_artifact_versions_created_at"), "artifact_versions", ["created_at"], unique=False)
    op.create_index(op.f("ix_artifact_versions_is_active"), "artifact_versions", ["is_active"], unique=False)
    op.create_index(op.f("ix_artifact_versions_restored_at"), "artifact_versions", ["restored_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_artifact_versions_restored_at'), table_name='artifact_versions')
    op.drop_index(op.f('ix_artifact_versions_is_active'), table_name='artifact_versions')
    op.drop_index(op.f('ix_artifact_versions_created_at'), table_name='artifact_versions')
    op.drop_index(op.f("ix_artifact_versions_artifact_id"), table_name="artifact_versions")
    op.drop_index(op.f("ix_artifact_versions_id"), table_name="artifact_versions")
    op.drop_table("artifact_versions")
    op.drop_index(op.f("ix_analysis_artifacts_id"), table_name="analysis_artifacts")
    op.drop_table("analysis_artifacts")
