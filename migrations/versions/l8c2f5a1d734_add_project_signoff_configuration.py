"""add project signoff configuration

Revision ID: l8c2f5a1d734
Revises: k7b5c1d9e023
Create Date: 2026-07-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l8c2f5a1d734"
down_revision: Union[str, Sequence[str], None] = "k7b5c1d9e023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("signoff_configuration", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "signoff_configuration")
