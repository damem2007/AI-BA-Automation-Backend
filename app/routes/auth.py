from fastapi import APIRouter

from app.services.rbac import CURRENT_SUPERADMIN, ROLE_PERMISSIONS


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/current-user")
def get_current_user():
    # Bootstrap identity until an external identity provider is connected.
    return CURRENT_SUPERADMIN


@router.get("/roles")
def get_roles():
    return ROLE_PERMISSIONS
