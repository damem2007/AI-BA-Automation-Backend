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
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_constraint("roles_name_key", "roles", type_="unique")
    op.create_index("ix_roles_name", "roles", ["name"])
    op.create_unique_constraint("uq_role_tenant_name", "roles", ["tenant_id", "name"])

    for column in ("external_subject", "username", "email"):
        op.drop_index(f"ix_users_{column}", table_name="users")
        op.drop_constraint(f"users_{column}_key", "users", type_="unique")
        op.create_index(f"ix_users_{column}", "users", [column])
    op.create_unique_constraint("uq_user_tenant_subject", "users", ["tenant_id", "external_subject"])
    op.create_unique_constraint("uq_user_tenant_username", "users", ["tenant_id", "username"])
    op.create_unique_constraint("uq_user_tenant_email", "users", ["tenant_id", "email"])

    op.drop_index("ix_teams_slug", table_name="teams")
    op.drop_constraint("teams_slug_key", "teams", type_="unique")
    op.create_index("ix_teams_slug", "teams", ["slug"])
    op.create_unique_constraint("uq_team_tenant_slug", "teams", ["tenant_id", "slug"])

    op.drop_constraint("identity_providers_issuer_key", "identity_providers", type_="unique")
    op.create_unique_constraint(
        "uq_provider_tenant_issuer", "identity_providers", ["tenant_id", "issuer"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_provider_tenant_issuer", "identity_providers", type_="unique")
    op.create_unique_constraint("identity_providers_issuer_key", "identity_providers", ["issuer"])

    op.drop_constraint("uq_team_tenant_slug", "teams", type_="unique")
    op.drop_index("ix_teams_slug", table_name="teams")
    op.create_unique_constraint("teams_slug_key", "teams", ["slug"])
    op.create_index("ix_teams_slug", "teams", ["slug"], unique=True)

    for constraint in ("uq_user_tenant_email", "uq_user_tenant_username", "uq_user_tenant_subject"):
        op.drop_constraint(constraint, "users", type_="unique")
    for column in ("external_subject", "username", "email"):
        op.drop_index(f"ix_users_{column}", table_name="users")
        op.create_unique_constraint(f"users_{column}_key", "users", [column])
        op.create_index(f"ix_users_{column}", "users", [column], unique=True)

    op.drop_constraint("uq_role_tenant_name", "roles", type_="unique")
    op.drop_index("ix_roles_name", table_name="roles")
    op.create_unique_constraint("roles_name_key", "roles", ["name"])
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)
