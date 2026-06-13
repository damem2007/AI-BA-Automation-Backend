from typing import Literal

from pydantic import BaseModel, Field


AppRole = Literal["superadmin", "admin", "business_analyst", "viewer"]
AppPermission = Literal[
    "manage_users",
    "manage_roles",
    "manage_projects",
    "create_analysis",
    "edit_artifacts",
    "approve_requirements",
    "view_artifacts",
]


class CurrentUser(BaseModel):
    id: str
    name: str
    username: str
    email: str
    role: AppRole
    permissions: list[AppPermission] = Field(default_factory=list)
