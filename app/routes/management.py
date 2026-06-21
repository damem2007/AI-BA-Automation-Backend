import re
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

import httpx

from app.models import (
    AnalysisArtifact,
    ArtifactVersion,
    IdentityProvider,
    ProjectTeam,
    Role,
    Team,
    TeamMembership,
    TenantSettings,
    Tenant,
    User,
)
from app.schemas.auth import (
    CurrentUser,
    IdentityProviderCreate,
    ProjectTeamsUpdate,
    RoleCreate,
    RoleUpdate,
    TeamCreate,
    TeamUpdate,
    TeamMembersUpdate,
    TenantCreate,
    TenantSettingsUpdate,
    UserCreate,
    UserUpdate,
)
from app.services.auth import (
    get_auth_db,
    get_current_user,
    create_password_reset_token,
    ensure_tenant_settings,
    generate_temporary_password,
    require_permission,
    require_any_permission,
    set_local_password,
)
from app.services.email_service import send_local_onboarding, send_sso_onboarding
from app.services.rbac import ROLE_PERMISSIONS


teams_router = APIRouter(prefix="/teams", tags=["teams"])
settings_router = APIRouter(prefix="/settings", tags=["settings"])
ALL_PERMISSIONS = sorted(
    {permission for permissions in ROLE_PERMISSIONS.values() for permission in permissions}
)


@settings_router.get("/tenants")
def list_tenants(
    actor: CurrentUser = Depends(require_permission("manage_tenants")),
    db: Session = Depends(get_auth_db),
):
    if not actor.is_global:
        raise HTTPException(status_code=403, detail="Global administration is required")
    return [
        {"id": tenant.id, "name": tenant.name, "status": tenant.status, "created_at": tenant.created_at}
        for tenant in db.query(Tenant).order_by(Tenant.name.asc()).all()
    ]


@settings_router.post("/tenants")
def create_tenant(
    request: TenantCreate,
    actor: CurrentUser = Depends(require_permission("manage_tenants")),
    db: Session = Depends(get_auth_db),
):
    if not actor.is_global:
        raise HTTPException(status_code=403, detail="Global administration is required")
    tenant_id = slugify(request.id)
    if db.query(Tenant).filter(Tenant.id == tenant_id).first():
        raise HTTPException(status_code=409, detail="Organization ID already exists")
    tenant = Tenant(id=tenant_id, name=request.name.strip(), status="active")
    db.add(tenant)
    db.add(TenantSettings(tenant_id=tenant_id))
    db.commit()
    db.refresh(tenant)
    return {"id": tenant.id, "name": tenant.name, "status": tenant.status, "created_at": tenant.created_at}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "team"


def unique_team_slug(db: Session, tenant_id: str, name: str, exclude_id: Optional[int] = None) -> str:
    base = slugify(name)
    slug = base
    suffix = 2
    while True:
        query = db.query(Team).filter(Team.slug == slug, Team.tenant_id == tenant_id)
        if exclude_id is not None:
            query = query.filter(Team.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def serialize_role(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "permissions": role.permissions or [],
        "is_system": role.is_system,
        "is_archived": role.is_archived,
        "tenant_id": role.tenant_id,
    }


def team_avatar(team: Team) -> dict:
    palette = ["#147d92", "#7c3aed", "#b45309", "#047857", "#be123c", "#3f6212"]
    icons = ["users", "blocks", "workflow", "layers", "briefcase", "network"]
    return {"color": palette[team.id % len(palette)], "icon": icons[team.id % len(icons)]}


def user_teams(db: Session, user_id: str) -> list[dict]:
    teams = db.query(Team).join(TeamMembership, TeamMembership.team_id == Team.id).filter(
        TeamMembership.user_id == user_id,
        Team.is_archived.is_(False),
    ).order_by(Team.name.asc()).all()
    return [{"id": team.id, "name": team.name, **team_avatar(team)} for team in teams]


def serialize_user(db: Session, user: User, role: Role) -> dict:
    return {
        "id": user.id,
        "subject": user.external_subject or user.id,
        "name": user.name,
        "username": user.username,
        "email": user.email,
        "tenant_id": user.tenant_id,
        "role": role.name,
        "permissions": role.permissions or [],
        "is_active": user.is_active,
        "is_archived": user.is_archived,
        "is_global": user.is_global,
        "auth_source": user.auth_source,
        "status": user.status,
        "password_expires_at": user.password_expires_at,
        "onboarding_status": user.onboarding_status,
        "teams": user_teams(db, user.id),
        "created_at": user.created_at,
    }


def serialize_team(db: Session, team: Team, current_user: CurrentUser) -> dict:
    membership = db.query(TeamMembership).filter(
        TeamMembership.team_id == team.id,
        TeamMembership.user_id == current_user.id,
    ).first()
    projects = db.query(AnalysisArtifact).join(ProjectTeam, ProjectTeam.artifact_id == AnalysisArtifact.id).filter(
        ProjectTeam.team_id == team.id,
        AnalysisArtifact.is_archived.is_(False),
    ).order_by(AnalysisArtifact.project_name.asc()).all()
    members = db.query(User).join(TeamMembership, TeamMembership.user_id == User.id).filter(
        TeamMembership.team_id == team.id,
        User.is_archived.is_(False),
    ).order_by(User.name.asc()).all()
    return {
        "id": team.id,
        "name": team.name,
        "slug": team.slug,
        "description": team.description,
        "owner_user_id": team.owner_user_id,
        "tenant_id": team.tenant_id,
        "allow_multiple_projects": team.allow_multiple_projects,
        "avatar": team_avatar(team),
        "membership_role": membership.membership_role if membership else None,
        "is_archived": team.is_archived,
        "project_count": len(projects),
        "projects": [
            {
                "id": project.id,
                "project_name": project.project_name,
                "project_code": project.project_code,
                "avatar_initials": project.avatar_initials,
                "avatar_color": project.avatar_color,
            }
            for project in projects
        ],
        "members": [{"id": member.id, "name": member.name, "email": member.email} for member in members],
        "created_at": team.created_at,
    }


def get_team_for_edit(db: Session, team_id: int, user: CurrentUser) -> Team:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    membership = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == user.id,
        TeamMembership.membership_role.in_(["owner", "admin"]),
    ).first()
    if not user.is_global and (team.tenant_id != user.tenant_id or not membership):
        raise HTTPException(status_code=403, detail="Team owner or admin access is required")
    return team


@teams_router.get("")
def list_teams(
    include_archived: bool = False,
    user: CurrentUser = Depends(require_permission("view_teams")),
    db: Session = Depends(get_auth_db),
):
    query = db.query(Team)
    if not user.is_global:
        query = query.filter(Team.tenant_id == user.tenant_id)
        team_ids = db.query(TeamMembership.team_id).filter(TeamMembership.user_id == user.id)
        query = query.filter(or_(Team.owner_user_id == user.id, Team.id.in_(team_ids)))
    if not include_archived:
        query = query.filter(Team.is_archived.is_(False))
    teams = query.order_by(Team.name.asc()).all()
    return [serialize_team(db, team, user) for team in teams]


@teams_router.post("")
def create_team(
    request: TeamCreate,
    user: CurrentUser = Depends(require_permission("create_teams")),
    db: Session = Depends(get_auth_db),
):
    name = request.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Team name must contain at least two characters")
    team = Team(
        name=name,
        slug=unique_team_slug(db, user.tenant_id, name),
        description=request.description.strip(),
        owner_user_id=user.id,
        tenant_id=user.tenant_id,
        allow_multiple_projects=request.allow_multiple_projects,
    )
    db.add(team)
    db.flush()
    db.add(TeamMembership(team_id=team.id, user_id=user.id, tenant_id=user.tenant_id, membership_role="owner"))
    db.commit()
    db.refresh(team)
    return serialize_team(db, team, user)


@teams_router.get("/{team_id}")
def get_team(
    team_id: int,
    user: CurrentUser = Depends(require_permission("view_teams")),
    db: Session = Depends(get_auth_db),
):
    team = db.query(Team).filter(Team.id == team_id, Team.is_archived.is_(False)).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not user.is_global:
        membership = db.query(TeamMembership).filter(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user.id,
        ).first()
        if not membership and team.owner_user_id != user.id:
            raise HTTPException(status_code=403, detail="Team access is required")
    return serialize_team(db, team, user)


@teams_router.put("/{team_id}/members")
def update_team_members(
    team_id: int,
    request: TeamMembersUpdate,
    user: CurrentUser = Depends(require_permission("manage_team_members")),
    db: Session = Depends(get_auth_db),
):
    team = get_team_for_edit(db, team_id, user)
    users = db.query(User).filter(
        User.id.in_(request.user_ids),
        User.tenant_id == team.tenant_id,
        User.is_archived.is_(False),
    ).all() if request.user_ids else []
    allowed_ids = {item.id for item in users}
    if allowed_ids != set(request.user_ids):
        raise HTTPException(status_code=422, detail="One or more users are not available in this tenant")
    allowed_ids.add(team.owner_user_id)
    db.query(TeamMembership).filter(
        TeamMembership.team_id == team.id,
        TeamMembership.user_id != team.owner_user_id,
    ).delete(synchronize_session=False)
    existing_owner = db.query(TeamMembership).filter(
        TeamMembership.team_id == team.id,
        TeamMembership.user_id == team.owner_user_id,
    ).first()
    if not existing_owner:
        db.add(TeamMembership(team_id=team.id, user_id=team.owner_user_id, tenant_id=team.tenant_id, membership_role="owner"))
    for user_id in sorted(allowed_ids - {team.owner_user_id}):
        db.add(TeamMembership(team_id=team.id, user_id=user_id, tenant_id=team.tenant_id, membership_role="member"))
    db.commit()
    return serialize_team(db, team, user)


@teams_router.put("/{team_id}")
def update_team(
    team_id: int,
    request: TeamUpdate,
    user: CurrentUser = Depends(require_permission("edit_teams")),
    db: Session = Depends(get_auth_db),
):
    team = get_team_for_edit(db, team_id, user)
    if team.is_archived:
        raise HTTPException(status_code=409, detail="Restore the team before editing it")
    if request.name is not None:
        name = request.name.strip()
        if len(name) < 2:
            raise HTTPException(status_code=422, detail="Team name must contain at least two characters")
        team.name = name
        team.slug = unique_team_slug(db, team.tenant_id, name, team.id)
    if request.description is not None:
        team.description = request.description.strip()
    if request.allow_multiple_projects is not None:
        if not request.allow_multiple_projects:
            project_count = db.query(ProjectTeam.artifact_id).filter(
                ProjectTeam.team_id == team.id
            ).distinct().count()
            if project_count > 1:
                raise HTTPException(
                    status_code=409,
                    detail="Remove this team from all but one project before disabling multi-project work",
                )
        team.allow_multiple_projects = request.allow_multiple_projects
    db.commit()
    db.refresh(team)
    return serialize_team(db, team, user)


@teams_router.post("/{team_id}/archive")
def archive_team(
    team_id: int,
    user: CurrentUser = Depends(require_permission("archive_teams")),
    db: Session = Depends(get_auth_db),
):
    team = get_team_for_edit(db, team_id, user)
    team.is_archived = True
    team.archived_at = datetime.now(timezone.utc)
    team.archived_by = user.id
    db.commit()
    return {"message": "Team archived. Assigned projects remain retained."}


@teams_router.post("/{team_id}/restore")
def restore_team(
    team_id: int,
    user: CurrentUser = Depends(require_permission("restore_archives")),
    db: Session = Depends(get_auth_db),
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not user.is_global and team.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Team not found")
    team.is_archived = False
    team.archived_at = None
    team.archived_by = None
    db.commit()
    return serialize_team(db, team, user)


@settings_router.get("/users")
def list_users(
    include_archived: bool = False,
    actor: CurrentUser = Depends(require_any_permission("manage_users", "manage_team_members")),
    db: Session = Depends(get_auth_db),
):
    query = db.query(User, Role).join(Role, Role.id == User.role_id)
    if not actor.is_global:
        query = query.filter(User.tenant_id == actor.tenant_id, User.is_global.is_(False))
    if not include_archived:
        query = query.filter(User.is_archived.is_(False))
    return [serialize_user(db, user, role) for user, role in query.order_by(User.name.asc()).all()]


@settings_router.post("/users")
def create_user(
    request: UserCreate,
    actor: CurrentUser = Depends(require_permission("manage_users")),
    db: Session = Depends(get_auth_db),
):
    if db.query(User).filter(
        User.tenant_id == actor.tenant_id,
        or_(User.email == request.email.lower(), User.username == request.username),
    ).first():
        raise HTTPException(status_code=409, detail="Email or username already exists")
    role = db.query(Role).filter(
        Role.name == request.role,
        Role.is_archived.is_(False),
        or_(Role.tenant_id.is_(None), Role.tenant_id == actor.tenant_id),
    ).first()
    if not role:
        raise HTTPException(status_code=422, detail="Role is not available")
    if request.auth_source == "local" and not request.password:
        raise HTTPException(status_code=422, detail="A password is required for local users")
    settings = ensure_tenant_settings(db, actor.tenant_id)
    user = User(
        id=f"user-{uuid4()}",
        tenant_id=actor.tenant_id,
        name=request.name.strip(),
        username=request.username.strip(),
        email=request.email.lower().strip(),
        role_id=role.id,
        auth_source=request.auth_source,
        status="active",
        onboarding_status="pending",
    )
    if request.auth_source == "local":
        set_local_password(user, request.password or "", settings)
    db.add(user)
    db.flush()
    reset_token = create_password_reset_token(db, user) if request.auth_source == "local" else None
    db.commit()
    db.refresh(user)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    if request.auth_source == "local":
        delivered = send_local_onboarding(user.email, user.name, f"{frontend_url}/reset-password?token={reset_token}")
    else:
        delivered = send_sso_onboarding(user.email, user.name, "enterprise SSO")
    user.onboarding_status = "email_sent" if delivered else "email_pending_configuration"
    db.commit()
    return serialize_user(db, user, role)


@settings_router.put("/users/{user_id}")
def update_user(
    user_id: str,
    request: UserUpdate,
    actor: CurrentUser = Depends(require_permission("manage_users")),
    db: Session = Depends(get_auth_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not actor.is_global and user.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    if request.name is not None:
        user.name = request.name.strip()
    if request.username is not None:
        user.username = request.username.strip()
    if request.role is not None:
        if user.id == "user-root-local" and request.role != "superadmin":
            raise HTTPException(status_code=409, detail="The local root role cannot be reduced")
        role = db.query(Role).filter(
            Role.name == request.role,
            Role.is_archived.is_(False),
            or_(Role.tenant_id.is_(None), Role.tenant_id == user.tenant_id),
        ).first()
        if not role:
            raise HTTPException(status_code=422, detail="Role is not available")
        user.role_id = role.id
    if request.is_active is not None:
        if user.id == actor.id and not request.is_active:
            raise HTTPException(status_code=409, detail="You cannot deactivate your own account")
        user.is_active = request.is_active
        user.status = "active" if request.is_active else "inactive"
    if request.password:
        if user.auth_source != "local":
            raise HTTPException(status_code=409, detail="SSO users do not have local passwords")
        set_local_password(user, request.password, ensure_tenant_settings(db, user.tenant_id))
    db.commit()
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return serialize_user(db, user, role)


@settings_router.post("/users/{user_id}/resend-onboarding")
def resend_user_onboarding(
    user_id: str,
    actor: CurrentUser = Depends(require_permission("manage_users")),
    db: Session = Depends(get_auth_db),
):
    user = db.query(User).filter(User.id == user_id, User.is_archived.is_(False)).first()
    if not user or (not actor.is_global and user.tenant_id != actor.tenant_id):
        raise HTTPException(status_code=404, detail="User not found")
    if user.onboarding_status not in {"pending", "email_pending_configuration"}:
        raise HTTPException(status_code=409, detail="Onboarding is not pending for this user")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    try:
        if user.auth_source == "local":
            reset_token = create_password_reset_token(db, user)
            delivered = send_local_onboarding(
                user.email,
                user.name,
                f"{frontend_url}/reset-password?token={reset_token}",
            )
        else:
            delivered = send_sso_onboarding(user.email, user.name, "enterprise SSO")
    except (OSError, RuntimeError):
        delivered = False
    user.onboarding_status = "email_sent" if delivered else "email_pending_configuration"
    db.commit()
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return {
        "message": "Onboarding email sent" if delivered else "Email service is not configured; invitation remains pending",
        "delivered": delivered,
        "user": serialize_user(db, user, role),
    }


@settings_router.post("/users/{user_id}/archive")
def archive_user(
    user_id: str,
    actor: CurrentUser = Depends(require_permission("manage_users")),
    db: Session = Depends(get_auth_db),
):
    if user_id == actor.id:
        raise HTTPException(status_code=409, detail="You cannot archive your own account")
    if user_id == "user-root-local":
        raise HTTPException(status_code=409, detail="The local root account cannot be archived")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not actor.is_global and user.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_archived = True
    user.is_active = False
    user.status = "archived"
    db.commit()
    return {"message": "User archived"}


@settings_router.post("/users/{user_id}/restore")
def restore_user(
    user_id: str,
    actor: CurrentUser = Depends(require_permission("restore_archives")),
    db: Session = Depends(get_auth_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not actor.is_global and user.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_archived = False
    user.is_active = True
    user.status = "active"
    db.commit()
    return {"message": "User restored"}


@settings_router.get("/roles")
def list_roles(
    actor: CurrentUser = Depends(
        require_any_permission("manage_roles", "manage_users", "manage_identity_providers")
    ),
    db: Session = Depends(get_auth_db),
):
    return {
        "permissions": ALL_PERMISSIONS,
        "roles": [
            serialize_role(role)
            for role in db.query(Role).filter(
                or_(Role.tenant_id.is_(None), Role.tenant_id == actor.tenant_id)
            ).order_by(Role.name.asc()).all()
        ],
    }


@settings_router.post("/roles")
def create_role(
    request: RoleCreate,
    actor: CurrentUser = Depends(require_permission("create_roles")),
    db: Session = Depends(get_auth_db),
):
    name = slugify(request.name).replace("-", "_")
    if db.query(Role).filter(
        Role.name == name,
        or_(Role.tenant_id.is_(None), Role.tenant_id == actor.tenant_id),
    ).first():
        raise HTTPException(status_code=409, detail="Role name already exists")
    unknown = sorted(set(request.permissions) - set(ALL_PERMISSIONS))
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown permissions: {', '.join(unknown)}")
    role = Role(
        name=name,
        description=request.description.strip(),
        permissions=sorted(set(request.permissions)),
        is_system=False,
        tenant_id=actor.tenant_id,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return serialize_role(role)


@settings_router.put("/roles/{role_name}")
def update_role(
    role_name: str,
    request: RoleUpdate,
    actor: CurrentUser = Depends(require_permission("manage_access")),
    db: Session = Depends(get_auth_db),
):
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if not actor.is_global and role.tenant_id not in {None, actor.tenant_id}:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.name == "superadmin" and request.permissions is not None:
        raise HTTPException(status_code=409, detail="Superadmin access policy is immutable")
    if request.permissions is not None:
        unknown = sorted(set(request.permissions) - set(ALL_PERMISSIONS))
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown permissions: {', '.join(unknown)}")
        role.permissions = sorted(set(request.permissions))
    if request.description is not None:
        role.description = request.description.strip()
    db.commit()
    db.refresh(role)
    return serialize_role(role)


@settings_router.get("/archive")
def list_archive(
    user: CurrentUser = Depends(require_permission("restore_archives")),
    db: Session = Depends(get_auth_db),
):
    projects = db.query(AnalysisArtifact).filter(AnalysisArtifact.is_archived.is_(True)).order_by(
        AnalysisArtifact.archived_at.desc()
    ).all()
    teams = db.query(Team).filter(Team.is_archived.is_(True)).order_by(Team.archived_at.desc()).all()
    users = db.query(User, Role).join(Role, Role.id == User.role_id).filter(User.is_archived.is_(True)).all()
    if not user.is_global:
        projects = [item for item in projects if item.tenant_id == user.tenant_id]
        teams = [item for item in teams if item.tenant_id == user.tenant_id]
        users = [(item, role) for item, role in users if item.tenant_id == user.tenant_id]
    return {
        "projects": [
            {
                "id": project.id,
                "project_name": project.project_name,
                "project_code": project.project_code,
                "avatar_initials": project.avatar_initials,
                "avatar_color": project.avatar_color,
                "team_id": project.team_id,
                "archived_at": project.archived_at,
                "archived_by": project.archived_by,
            }
            for project in projects
        ],
        "teams": [serialize_team(db, team, user) for team in teams],
        "users": [serialize_user(db, item, role) for item, role in users],
    }


@settings_router.get("/archive-impact/{resource_type}/{resource_id}")
def get_archive_impact(
    resource_type: str,
    resource_id: str,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_auth_db),
):
    permission_by_type = {
        "project": "archive_projects",
        "team": "archive_teams",
        "user": "manage_users",
    }
    permission = permission_by_type.get(resource_type)
    if not permission or permission not in actor.permissions:
        raise HTTPException(status_code=403, detail="Archive impact access is not permitted")

    dependencies = []
    if resource_type == "project":
        artifact = db.query(AnalysisArtifact).filter(AnalysisArtifact.id == int(resource_id)).first()
        if not artifact or (not actor.is_global and artifact.tenant_id != actor.tenant_id):
            raise HTTPException(status_code=404, detail="Project not found")
        version_count = db.query(ArtifactVersion).filter(ArtifactVersion.artifact_id == artifact.id).count()
        team_count = db.query(ProjectTeam).filter(ProjectTeam.artifact_id == artifact.id).count()
        relationship_count = len((artifact.analysis_json or {}).get("entity_relationships") or [])
        dependencies = [
            f"{version_count} retained version{'s' if version_count != 1 else ''}",
            f"{team_count} assigned team{'s' if team_count != 1 else ''}",
            f"{relationship_count} canonical relationship{'s' if relationship_count != 1 else ''}",
            f"{len(artifact.source_files or [])} source metadata record{'s' if len(artifact.source_files or []) != 1 else ''}",
        ]
        name = artifact.project_name
    elif resource_type == "team":
        team = db.query(Team).filter(Team.id == int(resource_id)).first()
        if not team or (not actor.is_global and team.tenant_id != actor.tenant_id):
            raise HTTPException(status_code=404, detail="Team not found")
        member_count = db.query(TeamMembership).filter(TeamMembership.team_id == team.id).count()
        project_count = db.query(ProjectTeam).filter(ProjectTeam.team_id == team.id).count()
        dependencies = [
            f"{member_count} retained member mapping{'s' if member_count != 1 else ''}",
            f"{project_count} retained project assignment{'s' if project_count != 1 else ''}",
        ]
        name = team.name
    else:
        user = db.query(User).filter(User.id == resource_id).first()
        if not user or (not actor.is_global and user.tenant_id != actor.tenant_id):
            raise HTTPException(status_code=404, detail="User not found")
        membership_count = db.query(TeamMembership).filter(TeamMembership.user_id == user.id).count()
        owned_team_count = db.query(Team).filter(Team.owner_user_id == user.id).count()
        owned_project_count = db.query(AnalysisArtifact).filter(AnalysisArtifact.owner_user_id == user.id).count()
        dependencies = [
            f"{membership_count} retained team membership{'s' if membership_count != 1 else ''}",
            f"{owned_team_count} owned team{'s' if owned_team_count != 1 else ''}",
            f"{owned_project_count} owned project{'s' if owned_project_count != 1 else ''}",
        ]
        name = user.name

    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "name": name,
        "dependencies": dependencies,
        "orphan_risk": False,
        "retention_note": "Archive is reversible and retains linked records; no relationship is deleted.",
    }


@settings_router.post("/archive/projects/{artifact_id}")
def archive_project(
    artifact_id: int,
    user: CurrentUser = Depends(require_permission("archive_projects")),
    db: Session = Depends(get_auth_db),
):
    artifact = db.query(AnalysisArtifact).filter(AnalysisArtifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Project not found")
    if not user.is_global and artifact.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Project not found")
    artifact.is_archived = True
    artifact.archived_at = datetime.now(timezone.utc)
    artifact.archived_by = user.id
    db.commit()
    return {"message": "Project archived"}


@settings_router.post("/archive/projects/{artifact_id}/restore")
def restore_project(
    artifact_id: int,
    actor: CurrentUser = Depends(require_permission("restore_archives")),
    db: Session = Depends(get_auth_db),
):
    artifact = db.query(AnalysisArtifact).filter(AnalysisArtifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Project not found")
    if not actor.is_global and artifact.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="Project not found")
    artifact.is_archived = False
    artifact.archived_at = None
    artifact.archived_by = None
    db.commit()
    return {"message": "Project restored"}


def serialize_tenant_settings(settings: TenantSettings) -> dict:
    return {
        "tenant_id": settings.tenant_id,
        "password_min_length": settings.password_min_length,
        "password_require_uppercase": settings.password_require_uppercase,
        "password_require_lowercase": settings.password_require_lowercase,
        "password_require_number": settings.password_require_number,
        "password_require_special": settings.password_require_special,
        "password_expiration_days": settings.password_expiration_days,
    }


@settings_router.get("/tenant-policy")
def get_tenant_policy(
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_auth_db),
):
    return serialize_tenant_settings(ensure_tenant_settings(db, actor.tenant_id))


@settings_router.put("/tenant-policy")
def update_tenant_policy(
    request: TenantSettingsUpdate,
    actor: CurrentUser = Depends(require_permission("manage_password_policy")),
    db: Session = Depends(get_auth_db),
):
    settings = ensure_tenant_settings(db, actor.tenant_id)
    for key, value in request.model_dump(exclude_none=True).items():
        setattr(settings, key, value)
    if settings.password_min_length < 8 or settings.password_min_length > 128:
        raise HTTPException(status_code=422, detail="Password length must be between 8 and 128")
    if settings.password_expiration_days < 0 or settings.password_expiration_days > 730:
        raise HTTPException(status_code=422, detail="Password expiration must be between 0 and 730 days")
    db.commit()
    return serialize_tenant_settings(settings)


@settings_router.post("/password/generate")
def generate_password(
    actor: CurrentUser = Depends(require_permission("manage_users")),
    db: Session = Depends(get_auth_db),
):
    settings = ensure_tenant_settings(db, actor.tenant_id)
    return {"password": generate_temporary_password(settings)}


@settings_router.get("/project-team-mapping")
def get_project_team_mapping(
    actor: CurrentUser = Depends(require_permission("assign_project_teams")),
    db: Session = Depends(get_auth_db),
):
    project_query = db.query(AnalysisArtifact).filter(AnalysisArtifact.is_archived.is_(False))
    team_query = db.query(Team).filter(Team.is_archived.is_(False))
    if not actor.is_global:
        project_query = project_query.filter(AnalysisArtifact.tenant_id == actor.tenant_id)
        team_query = team_query.filter(Team.tenant_id == actor.tenant_id)
    projects = project_query.order_by(AnalysisArtifact.project_name.asc()).all()
    teams = team_query.order_by(Team.name.asc()).all()
    assignments = db.query(ProjectTeam).filter(ProjectTeam.artifact_id.in_([item.id for item in projects])).all() if projects else []
    by_project = {}
    for assignment in assignments:
        by_project.setdefault(assignment.artifact_id, []).append(assignment.team_id)
    return {
        "projects": [
            {
                "id": project.id,
                "project_name": project.project_name,
                "project_code": project.project_code,
                "avatar_initials": project.avatar_initials,
                "avatar_color": project.avatar_color,
                "team_ids": by_project.get(project.id, []),
            }
            for project in projects
        ],
        "teams": [
            {
                "id": team.id,
                "name": team.name,
                "allow_multiple_projects": team.allow_multiple_projects,
                "avatar": team_avatar(team),
            }
            for team in teams
        ],
    }


@settings_router.put("/projects/{artifact_id}/teams")
def update_project_teams(
    artifact_id: int,
    request: ProjectTeamsUpdate,
    actor: CurrentUser = Depends(require_permission("assign_project_teams")),
    db: Session = Depends(get_auth_db),
):
    artifact = db.query(AnalysisArtifact).filter(AnalysisArtifact.id == artifact_id).first()
    if not artifact or (not actor.is_global and artifact.tenant_id != actor.tenant_id):
        raise HTTPException(status_code=404, detail="Project not found")
    team_ids = list(dict.fromkeys(request.team_ids))
    teams = db.query(Team).filter(
        Team.id.in_(team_ids),
        Team.tenant_id == artifact.tenant_id,
        Team.is_archived.is_(False),
    ).all() if team_ids else []
    if {team.id for team in teams} != set(team_ids):
        raise HTTPException(status_code=422, detail="One or more teams are not available")
    for team in teams:
        existing_project = db.query(ProjectTeam).filter(
            ProjectTeam.team_id == team.id,
            ProjectTeam.artifact_id != artifact.id,
        ).first()
        if existing_project and not team.allow_multiple_projects:
            raise HTTPException(
                status_code=409,
                detail=f"{team.name} is limited to one project. Enable multi-project work in Team settings.",
            )
    db.query(ProjectTeam).filter(ProjectTeam.artifact_id == artifact.id).delete(synchronize_session=False)
    for team_id in team_ids:
        db.add(ProjectTeam(artifact_id=artifact.id, team_id=team_id, tenant_id=artifact.tenant_id, assigned_by=actor.id))
    artifact.team_id = team_ids[0] if team_ids else None
    db.commit()
    return {"message": "Project team assignments updated", "team_ids": team_ids}


def serialize_identity_provider(provider: IdentityProvider) -> dict:
    return {
        "id": provider.id,
        "tenant_id": provider.tenant_id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "issuer": provider.issuer,
        "audience": provider.audience,
        "jwks_url": provider.jwks_url,
        "required_scopes": provider.required_scopes or [],
        "users_endpoint": provider.users_endpoint,
        "token_env_key": provider.token_env_key,
        "icon_key": provider.icon_key,
        "default_role": provider.default_role,
        "is_active": provider.is_active,
        "last_synced_at": provider.last_synced_at,
    }


@settings_router.get("/identity-providers")
def list_identity_providers(
    actor: CurrentUser = Depends(require_permission("manage_identity_providers")),
    db: Session = Depends(get_auth_db),
):
    query = db.query(IdentityProvider)
    if not actor.is_global:
        query = query.filter(IdentityProvider.tenant_id == actor.tenant_id)
    return [serialize_identity_provider(provider) for provider in query.order_by(IdentityProvider.name.asc()).all()]


@settings_router.post("/identity-providers")
def create_identity_provider(
    request: IdentityProviderCreate,
    actor: CurrentUser = Depends(require_permission("manage_identity_providers")),
    db: Session = Depends(get_auth_db),
):
    if db.query(IdentityProvider).filter(
        IdentityProvider.issuer == request.issuer,
        IdentityProvider.tenant_id == actor.tenant_id,
    ).first():
        raise HTTPException(status_code=409, detail="Identity provider issuer already exists")
    provider = IdentityProvider(tenant_id=actor.tenant_id, **request.model_dump())
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return serialize_identity_provider(provider)


@settings_router.post("/identity-providers/{provider_id}/sync")
def sync_identity_provider(
    provider_id: int,
    actor: CurrentUser = Depends(require_permission("manage_identity_providers")),
    db: Session = Depends(get_auth_db),
):
    provider = db.query(IdentityProvider).filter(IdentityProvider.id == provider_id).first()
    if not provider or (not actor.is_global and provider.tenant_id != actor.tenant_id):
        raise HTTPException(status_code=404, detail="Identity provider not found")
    if not provider.users_endpoint or not provider.token_env_key:
        raise HTTPException(status_code=409, detail="User sync endpoint and token environment key are required")
    provider_token = os.getenv(provider.token_env_key, "")
    if not provider_token:
        raise HTTPException(status_code=503, detail=f"Environment secret {provider.token_env_key} is not configured")
    try:
        response = httpx.get(
            provider.users_endpoint,
            headers={"Authorization": f"Bearer {provider_token}"},
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Identity provider user synchronization failed") from error
    payload = response.json()
    records = payload if isinstance(payload, list) else payload.get("value") or payload.get("users") or []
    role = db.query(Role).filter(
        Role.name == provider.default_role,
        or_(Role.tenant_id.is_(None), Role.tenant_id == provider.tenant_id),
    ).first()
    if not role:
        raise HTTPException(status_code=409, detail="Identity provider default role is unavailable")
    created = 0
    updated = 0
    skipped = 0
    for record in records:
        subject = str(record.get("id") or record.get("sub") or "")
        email = str(record.get("mail") or record.get("email") or record.get("userPrincipalName") or "").lower()
        if not subject or not email:
            continue
        user = db.query(User).filter(User.external_subject == subject, User.tenant_id == provider.tenant_id).first()
        email_user = db.query(User).filter(User.email == email, User.tenant_id == provider.tenant_id).first()
        if not user and email_user and email_user.auth_source == "local":
            # A local identity retains ownership of its email; directory sync reports the collision.
            skipped += 1
            continue
        if not user and email_user:
            user = email_user
            user.external_subject = subject
        name = str(record.get("displayName") or record.get("name") or email.split("@")[0])
        username_base = str(record.get("userPrincipalName") or record.get("preferred_username") or email).split("@")[0]
        if not user:
            username = username_base
            suffix = 2
            while db.query(User).filter(User.username == username, User.tenant_id == provider.tenant_id).first():
                username = f"{username_base}-{suffix}"
                suffix += 1
            user = User(
                id=f"user-{uuid4()}",
                external_subject=subject,
                tenant_id=provider.tenant_id,
                name=name,
                username=username,
                email=email,
                role_id=role.id,
                auth_source="sso",
                status="active",
                is_active=True,
                onboarding_status="synced",
            )
            db.add(user)
            created += 1
            send_sso_onboarding(email, name, provider.name)
        else:
            user.name = name
            user.email = email
            user.is_active = bool(record.get("accountEnabled", True))
            user.status = "active" if user.is_active else "inactive"
            updated += 1
    provider.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "message": "Identity users synchronized",
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }
