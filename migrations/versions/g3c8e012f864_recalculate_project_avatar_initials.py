"""recalculate project avatar initials

Revision ID: g3c8e012f864
Revises: f2b7d901e753
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.services.project_generator import get_initials


revision: str = "g3c8e012f864"
down_revision: Union[str, Sequence[str], None] = "f2b7d901e753"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    artifacts = connection.execute(
        sa.text("SELECT id, project_name FROM analysis_artifacts ORDER BY id")
    ).mappings().all()
    update_initials = sa.text(
        """
        UPDATE analysis_artifacts
        SET avatar_initials = :avatar_initials
        WHERE id = :artifact_id
        """
    )
    for artifact in artifacts:
        connection.execute(
            update_initials,
            {
                "artifact_id": artifact["id"],
                "avatar_initials": get_initials(artifact["project_name"] or ""),
            },
        )


def downgrade() -> None:
    # The previous values cannot be reconstructed reliably after recalculation.
    pass
