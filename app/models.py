from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("tenant_id", "project_code", name="uq_project_tenant_project_code"),)

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String, nullable=False)
    project_code = Column(String, nullable=False, index=True)
    avatar_initials = Column(String, nullable=False)
    avatar_color = Column(String, nullable=False)
    project_type = Column(String, nullable=False, default="internal", server_default="internal")
    company_name = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    initiative_type = Column(String, nullable=True)
    country = Column(String, nullable=True)
    signoff_configuration = Column(JSON, nullable=True)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String, nullable=False, default="local", server_default="local", index=True)
    is_deleted = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False, nullable=False, server_default="false", index=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archived_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AnalysisArtifact(Base):
    __tablename__ = "analysis_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    project_type = Column(String, nullable=False, default="internal", server_default="internal")
    company_name = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    analysis_focus_key = Column(String, nullable=True)
    analysis_focus_chapter = Column(String, nullable=True)
    analysis_focus_area = Column(String, nullable=True)
    selected_activity_keys = Column(JSON, nullable=True)
    selected_activity_labels = Column(JSON, nullable=True)
    selected_techniques = Column(JSON, nullable=True)
    infer_additional_techniques = Column(Boolean, default=True)
    selected_outputs = Column(JSON, nullable=True)
    source_files = Column(JSON, nullable=True)
    country = Column(String, nullable=True)
    transcript = Column(Text, nullable=False)
    analysis_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False, nullable=False, server_default="false", index=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archived_by = Column(String, nullable=True)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    tenant_id = Column(String, nullable=False, default="local", server_default="local", index=True)
    current_version_id = Column(Integer, nullable=True, index=True)


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"

    id = Column(Integer, primary_key=True, index=True)
    artifact_id = Column(Integer, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, default="local", server_default="local", index=True)
    analysis_json = Column(JSON, nullable=False)
    version_type = Column(String, default="snapshot")
    is_active = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    restored_at = Column(DateTime(timezone=True), nullable=True, index=True)
    current_version_id = Column(Integer, nullable=True, index=True)


class ArtifactApprovalAssignment(Base):
    __tablename__ = "artifact_approval_assignments"

    id = Column(Integer, primary_key=True)
    artifact_id = Column(Integer, ForeignKey("analysis_artifacts.id"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, default="local", server_default="local", index=True)
    assigned_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    requested_by_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    approval_level = Column(String, nullable=False, default="business")
    status = Column(String, nullable=False, default="pending", index=True)
    due_date = Column(String, nullable=True)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_role_tenant_name"),)

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(String, nullable=False, default="")
    permissions = Column(JSON, nullable=False, default=list)
    is_system = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False, index=True)
    tenant_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_subject", name="uq_user_tenant_subject"),
        UniqueConstraint("tenant_id", "username", name="uq_user_tenant_username"),
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    id = Column(String, primary_key=True)
    external_subject = Column(String, nullable=True, index=True)
    tenant_id = Column(String, nullable=False, default="local", index=True)
    name = Column(String, nullable=False)
    username = Column(String, nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    password_hash = Column(String, nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_archived = Column(Boolean, nullable=False, default=False, index=True)
    is_global = Column(Boolean, nullable=False, default=False)
    auth_source = Column(String, nullable=False, default="local")
    status = Column(String, nullable=False, default="active", index=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    password_expires_at = Column(DateTime(timezone=True), nullable=True)
    onboarding_status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_team_tenant_slug"),)

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)
    description = Column(String, nullable=False, default="")
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, default="local", server_default="local", index=True)
    allow_multiple_projects = Column(Boolean, nullable=False, default=False, server_default="false")
    is_archived = Column(Boolean, nullable=False, default=False, index=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archived_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TeamMembership(Base):
    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_membership"),)

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, default="local", server_default="local", index=True)
    membership_role = Column(String, nullable=False, default="member")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProjectTeam(Base):
    __tablename__ = "project_teams"
    __table_args__ = (UniqueConstraint("project_id", "team_id", name="uq_project_team"),)

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, default="local", server_default="local", index=True)
    assigned_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    tenant_id = Column(String, primary_key=True)
    password_min_length = Column(Integer, nullable=False, default=12)
    password_require_uppercase = Column(Boolean, nullable=False, default=True)
    password_require_lowercase = Column(Boolean, nullable=False, default=True)
    password_require_number = Column(Boolean, nullable=False, default=True)
    password_require_special = Column(Boolean, nullable=False, default=True)
    password_expiration_days = Column(Integer, nullable=False, default=90)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IdentityProvider(Base):
    __tablename__ = "identity_providers"
    __table_args__ = (UniqueConstraint("tenant_id", "issuer", name="uq_provider_tenant_issuer"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    provider_type = Column(String, nullable=False, default="oidc")
    issuer = Column(String, nullable=False)
    audience = Column(String, nullable=False)
    jwks_url = Column(String, nullable=False)
    required_scopes = Column(JSON, nullable=False, default=list)
    users_endpoint = Column(String, nullable=True)
    token_env_key = Column(String, nullable=True)
    icon_key = Column(String, nullable=False, default="key")
    default_role = Column(String, nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, default="local", server_default="local", index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
