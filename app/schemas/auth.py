from typing import Literal, Optional

from pydantic import BaseModel, Field


class CurrentUser(BaseModel):
    id: str
    subject: str
    tenant_id: str = "local"
    name: str
    username: str
    email: str
    role: str
    permissions: list[str] = Field(default_factory=list)
    is_global: bool = False
    auth_source: str = "local"
    token_expires_at: Optional[int] = None


class TokenRequest(BaseModel):
    email: str
    password: str
    tenant_id: str = "local"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUser


class UserCreate(BaseModel):
    name: str
    username: str
    email: str
    role: str
    password: Optional[str] = None
    auth_source: Literal["local", "sso"] = "local"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class RoleUpdate(BaseModel):
    description: Optional[str] = None
    permissions: Optional[list[str]] = None


class RoleCreate(BaseModel):
    name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class TeamCreate(BaseModel):
    name: str
    description: str = ""
    allow_multiple_projects: bool = False


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    allow_multiple_projects: Optional[bool] = None


class TeamMembersUpdate(BaseModel):
    user_ids: list[str] = Field(default_factory=list)


class ProjectTeamsUpdate(BaseModel):
    team_ids: list[int] = Field(default_factory=list)


class TenantSettingsUpdate(BaseModel):
    password_min_length: Optional[int] = None
    password_require_uppercase: Optional[bool] = None
    password_require_lowercase: Optional[bool] = None
    password_require_number: Optional[bool] = None
    password_require_special: Optional[bool] = None
    password_expiration_days: Optional[int] = None


class IdentityProviderCreate(BaseModel):
    name: str
    provider_type: str = "oidc"
    issuer: str
    audience: str
    jwks_url: str
    required_scopes: list[str] = Field(default_factory=lambda: ["access_as_user"])
    users_endpoint: Optional[str] = None
    token_env_key: Optional[str] = None
    icon_key: str = "key"
    default_role: str = "viewer"


class TenantCreate(BaseModel):
    id: str
    name: str


class PasswordResetRequest(BaseModel):
    token: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
