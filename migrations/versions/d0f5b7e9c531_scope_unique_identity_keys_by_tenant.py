"""scope unique identity keys by tenant

Revision ID: d0f5b7e9c531
Revises: c9e4a6d8b420
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d0f5b7e9c531"
down_revision: Union[str, Sequence[str], None] = "c9e4a6d8b420"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("roles") as batch:
        batch.drop_index("ix_roles_name")
        batch.drop_constraint("roles_name_key", type_="unique")
        batch.create_index("ix_roles_name", ["name"])
        batch.create_unique_constraint("uq_role_tenant_name", ["tenant_id", "name"])

    with op.batch_alter_table("users") as batch:
        for column in ("external_subject", "username", "email"):
            batch.drop_index(f"ix_users_{column}")
            batch.drop_constraint(f"users_{column}_key", type_="unique")
            batch.create_index(f"ix_users_{column}", [column])
        batch.create_unique_constraint("uq_user_tenant_subject", ["tenant_id", "external_subject"])
        batch.create_unique_constraint("uq_user_tenant_username", ["tenant_id", "username"])
        batch.create_unique_constraint("uq_user_tenant_email", ["tenant_id", "email"])

    with op.batch_alter_table("teams") as batch:
        batch.drop_index("ix_teams_slug")
        batch.drop_constraint("teams_slug_key", type_="unique")
        batch.create_index("ix_teams_slug", ["slug"])
        batch.create_unique_constraint("uq_team_tenant_slug", ["tenant_id", "slug"])

    with op.batch_alter_table("identity_providers") as batch:
        batch.drop_constraint("identity_providers_issuer_key", type_="unique")
        batch.create_unique_constraint("uq_provider_tenant_issuer", ["tenant_id", "issuer"])


def downgrade() -> None:
    with op.batch_alter_table("identity_providers") as batch:
        batch.drop_constraint("uq_provider_tenant_issuer", type_="unique")
        batch.create_unique_constraint("identity_providers_issuer_key", ["issuer"])

    with op.batch_alter_table("teams") as batch:
        batch.drop_constraint("uq_team_tenant_slug", type_="unique")
        batch.drop_index("ix_teams_slug")
        batch.create_unique_constraint("teams_slug_key", ["slug"])
        batch.create_index("ix_teams_slug", ["slug"], unique=True)

    with op.batch_alter_table("users") as batch:
        for constraint in ("uq_user_tenant_email", "uq_user_tenant_username", "uq_user_tenant_subject"):
            batch.drop_constraint(constraint, type_="unique")
        for column in ("external_subject", "username", "email"):
            batch.drop_index(f"ix_users_{column}")
            batch.create_unique_constraint(f"users_{column}_key", [column])
            batch.create_index(f"ix_users_{column}", [column], unique=True)

    with op.batch_alter_table("roles") as batch:
        batch.drop_constraint("uq_role_tenant_name", type_="unique")
        batch.drop_index("ix_roles_name")
        batch.create_unique_constraint("roles_name_key", ["name"])
        batch.create_index("ix_roles_name", ["name"], unique=True)
