from app.schemas.auth import CurrentUser


ROLE_PERMISSIONS = {
    "superadmin": [
        "manage_users",
        "manage_roles",
        "manage_projects",
        "create_analysis",
        "edit_artifacts",
        "approve_requirements",
        "view_artifacts",
    ],
    "admin": [
        "manage_projects",
        "create_analysis",
        "edit_artifacts",
        "approve_requirements",
        "view_artifacts",
    ],
    "business_analyst": [
        "create_analysis",
        "edit_artifacts",
        "approve_requirements",
        "view_artifacts",
    ],
    "viewer": ["view_artifacts"],
}


CURRENT_SUPERADMIN = CurrentUser(
    id="user-dami-dahunsi",
    name="Dami Dahunsi",
    username="damem2007",
    email="dami@ba-optimization.local",
    role="superadmin",
    permissions=ROLE_PERMISSIONS["superadmin"],
)
