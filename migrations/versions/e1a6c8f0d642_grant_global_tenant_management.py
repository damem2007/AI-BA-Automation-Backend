"""grant global tenant management

Revision ID: e1a6c8f0d642
Revises: d0f5b7e9c531
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e1a6c8f0d642"
down_revision: Union[str, Sequence[str], None] = "d0f5b7e9c531"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE roles
        SET permissions = (permissions::jsonb || '["manage_tenants"]'::jsonb)::json
        WHERE name = 'superadmin'
          AND tenant_id IS NULL
          AND NOT permissions::jsonb ? 'manage_tenants'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE roles
        SET permissions = (permissions::jsonb - 'manage_tenants')::json
        WHERE name = 'superadmin' AND tenant_id IS NULL
        """
    )
