"""add artifact approval assignments

Revision ID: k7b5c1d9e023
Revises: j6a4f0e8c912
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k7b5c1d9e023"
down_revision: Union[str, Sequence[str], None] = "j6a4f0e8c912"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "artifact_approval_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("artifact_id", sa.Integer(), sa.ForeignKey("analysis_artifacts.id"), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="local"),
        sa.Column("assigned_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approval_level", sa.String(), nullable=False, server_default="business"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("due_date", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_artifact_approvals_artifact_status", "artifact_approval_assignments", ["artifact_id", "status"])
    op.create_index("ix_artifact_approvals_assignee_status", "artifact_approval_assignments", ["assigned_user_id", "status"])
    op.create_index("ix_artifact_approvals_tenant_status", "artifact_approval_assignments", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_artifact_approvals_tenant_status", table_name="artifact_approval_assignments")
    op.drop_index("ix_artifact_approvals_assignee_status", table_name="artifact_approval_assignments")
    op.drop_index("ix_artifact_approvals_artifact_status", table_name="artifact_approval_assignments")
    op.drop_table("artifact_approval_assignments")
