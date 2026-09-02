"""grant global tenant management

Revision ID: e1a6c8f0d642
Revises: d0f5b7e9c531
Create Date: 2026-06-20
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1a6c8f0d642"
down_revision: Union[str, Sequence[str], None] = "d0f5b7e9c531"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, permissions FROM roles WHERE name = 'superadmin' AND tenant_id IS NULL")
    ).mappings().all()
    for row in rows:
        permissions = _permissions_list(row["permissions"])
        if "manage_tenants" not in permissions:
            permissions.append("manage_tenants")
            connection.execute(
                sa.text("UPDATE roles SET permissions = :permissions WHERE id = :id"),
                {"id": row["id"], "permissions": json.dumps(permissions)},
            )


def downgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, permissions FROM roles WHERE name = 'superadmin' AND tenant_id IS NULL")
    ).mappings().all()
    for row in rows:
        permissions = [item for item in _permissions_list(row["permissions"]) if item != "manage_tenants"]
        connection.execute(
            sa.text("UPDATE roles SET permissions = :permissions WHERE id = :id"),
            {"id": row["id"], "permissions": json.dumps(permissions)},
        )


def _permissions_list(value) -> list[str]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []
