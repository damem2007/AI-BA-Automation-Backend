import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Callable, Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import IdentityProvider, PasswordResetToken, Role, Tenant, TenantSettings, User
from app.schemas.auth import CurrentUser
from app.services.rbac import ROLE_DESCRIPTIONS, ROLE_PERMISSIONS


load_dotenv()

AUTH_MODE = os.getenv("AUTH_MODE", "hybrid").lower()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ISSUER = os.getenv("JWT_ISSUER", "ba-optimization-local")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "ba-optimization-api")
JWT_ACCESS_TOKEN_MINUTES = max(5, int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60")))
OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL", "")
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", JWT_AUDIENCE)
OIDC_ALGORITHMS = [
    algorithm.strip()
    for algorithm in os.getenv("OIDC_ALGORITHMS", "RS256").split(",")
    if algorithm.strip()
]
OIDC_TENANT_ID = os.getenv("OIDC_TENANT_ID", "")
OIDC_REQUIRED_SCOPES = {
    scope.strip()
    for scope in os.getenv("OIDC_REQUIRED_SCOPES", "access_as_user").split(",")
    if scope.strip()
}
LOCAL_ROOT_EMAIL = os.getenv("LOCAL_ROOT_EMAIL", "root@ba-optimization.local").lower()
LOCAL_ROOT_USERNAME = os.getenv("LOCAL_ROOT_USERNAME", "root")
LOCAL_ROOT_NAME = os.getenv("LOCAL_ROOT_NAME", "Local Root Administrator")
LOCAL_ROOT_PASSWORD = os.getenv("LOCAL_ROOT_PASSWORD", "")

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str, iterations: int = 600_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(digest).decode(),
    )


def verify_password(password: str, encoded: Optional[str]) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            base64.urlsafe_b64decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(
            base64.urlsafe_b64encode(digest).decode(),
            expected,
        )
    except (TypeError, ValueError):
        return False


def ensure_local_identity() -> None:
    db = SessionLocal()
    try:
        roles = {}
        for role_name, permissions in ROLE_PERMISSIONS.items():
            role = db.query(Role).filter(Role.name == role_name, Role.tenant_id.is_(None)).first()
            if not role:
                role = Role(
                    name=role_name,
                    description=ROLE_DESCRIPTIONS.get(role_name, ""),
                    permissions=permissions,
                    is_system=True,
                )
                db.add(role)
                db.flush()
            roles[role_name] = role

        # Global root always receives the complete platform permission set.
        roles["superadmin"].permissions = ROLE_PERMISSIONS["superadmin"]

        root = db.query(User).filter(User.email == LOCAL_ROOT_EMAIL, User.tenant_id == "local").first()
        if not root:
            if not LOCAL_ROOT_PASSWORD:
                raise RuntimeError("LOCAL_ROOT_PASSWORD must be configured before local auth starts")
            root = User(
                id="user-root-local",
                external_subject=None,
                tenant_id="local",
                name=LOCAL_ROOT_NAME,
                username=LOCAL_ROOT_USERNAME,
                email=LOCAL_ROOT_EMAIL,
                password_hash=hash_password(LOCAL_ROOT_PASSWORD),
                role_id=roles["superadmin"].id,
                is_active=True,
                is_archived=False,
                is_global=True,
                auth_source="local",
                status="active",
                password_changed_at=datetime.now(timezone.utc),
                onboarding_status="complete",
            )
            db.add(root)
        else:
            root.is_global = True
            root.auth_source = "local"
            root.status = "active"
        ensure_tenant_settings(db, "local")
        db.commit()
    finally:
        db.close()


def create_access_token(user: User, role: Role) -> tuple[str, int]:
    if not JWT_SECRET:
        raise HTTPException(status_code=503, detail="Local JWT signing is not configured")
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=JWT_ACCESS_TOKEN_MINUTES)
    payload = {
        "sub": user.id,
        "tid": user.tenant_id,
        "email": user.email,
        "preferred_username": user.username,
        "roles": [role.name],
        "permissions": role.permissions or [],
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": expires,
        "jti": secrets.token_urlsafe(16),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, JWT_ACCESS_TOKEN_MINUTES * 60


def decode_access_token(token: str, db: Session) -> dict:
    try:
        unverified_header = jwt.get_unverified_header(token)
        algorithm = unverified_header.get("alg")
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        token_issuer = str(unverified_claims.get("iss") or "")
        if token_issuer == JWT_ISSUER:
            if algorithm != JWT_ALGORITHM or not JWT_SECRET:
                raise jwt.InvalidTokenError("Token algorithm is not allowed")
            return jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[JWT_ALGORITHM],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub"]},
            )

        if AUTH_MODE == "local":
            raise jwt.InvalidTokenError("External identity tokens are disabled")
        provider = db.query(IdentityProvider).filter(
            IdentityProvider.issuer == token_issuer,
            IdentityProvider.is_active.is_(True),
        ).first()
        if not provider or algorithm not in OIDC_ALGORITHMS:
            raise jwt.InvalidTokenError("Identity provider is not trusted")
        signing_key = get_jwk_client(provider.jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=OIDC_ALGORITHMS,
            audience=provider.audience,
            issuer=provider.issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        if claims.get("tid") != provider.tenant_id:
            raise jwt.InvalidTokenError("Token tenant is not allowed")
        token_scopes = set(str(claims.get("scp") or "").split())
        token_roles = set(claims.get("roles") or [])
        required_scopes = set(provider.required_scopes or [])
        if required_scopes and not (required_scopes & token_scopes or token_roles):
            raise jwt.InvalidTokenError("Token does not contain an accepted API scope or role")
        return claims
    except jwt.PyJWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


@lru_cache(maxsize=16)
def get_jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)


def current_user_from_model(
    user: User,
    role: Role,
    subject: Optional[str] = None,
    token_expires_at: Optional[int] = None,
) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        subject=subject or user.external_subject or user.id,
        tenant_id=user.tenant_id,
        name=user.name,
        username=user.username,
        email=user.email,
        role=role.name,
        permissions=role.permissions or [],
        is_global=user.is_global,
        auth_source=user.auth_source,
        token_expires_at=token_expires_at,
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_auth_db),
) -> CurrentUser:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_access_token(credentials.credentials, db)
    subject = str(claims.get("sub") or "")
    tenant_id = str(claims.get("tid") or "local")
    if str(claims.get("iss") or "") == JWT_ISSUER:
        user = db.query(User).filter(User.id == subject).first()
    else:
        user = db.query(User).filter(User.external_subject == subject, User.tenant_id == tenant_id).first()
    if not user or not user.is_active or user.is_archived or user.status != "active":
        raise HTTPException(status_code=403, detail="User is not authorized for this workspace")
    if user.auth_source == "local" and password_is_expired(user):
        user.status = "password_expired"
        user.is_active = False
        db.commit()
        raise HTTPException(status_code=403, detail="Password has expired")
    role = db.query(Role).filter(Role.id == user.role_id, Role.is_archived.is_(False)).first()
    if not role:
        raise HTTPException(status_code=403, detail="User has no active role")
    return current_user_from_model(user, role, subject, claims.get("exp"))


def require_permission(permission: str) -> Callable:
    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if permission not in user.permissions:
            raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
        return user

    return dependency


def require_any_permission(*permissions: str) -> Callable:
    """Authorize delegated workflows that accept any one of several narrow permissions."""
    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(permissions).intersection(user.permissions):
            raise HTTPException(
                status_code=403,
                detail=f"One permission is required: {', '.join(permissions)}",
            )
        return user

    return dependency


def has_permission(user: CurrentUser, permission: str) -> bool:
    return user.is_global or permission in user.permissions


def ensure_tenant_settings(db: Session, tenant_id: str) -> TenantSettings:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        db.add(Tenant(id=tenant_id, name=tenant_id.replace("-", " ").title()))
        db.flush()
    settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant_id).first()
    if not settings:
        settings = TenantSettings(tenant_id=tenant_id)
        db.add(settings)
        db.flush()
    return settings


def validate_password_policy(password: str, settings: TenantSettings) -> list[str]:
    errors = []
    if len(password) < settings.password_min_length:
        errors.append(f"at least {settings.password_min_length} characters")
    if settings.password_require_uppercase and not any(value.isupper() for value in password):
        errors.append("an uppercase character")
    if settings.password_require_lowercase and not any(value.islower() for value in password):
        errors.append("a lowercase character")
    if settings.password_require_number and not any(value.isdigit() for value in password):
        errors.append("a number")
    if settings.password_require_special and not any(not value.isalnum() for value in password):
        errors.append("a special character")
    return errors


def generate_temporary_password(settings: TenantSettings) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(max(settings.password_min_length, 16)))
        if not validate_password_policy(password, settings):
            return password


def set_local_password(user: User, password: str, settings: TenantSettings) -> None:
    errors = validate_password_policy(password, settings)
    if errors:
        raise HTTPException(status_code=422, detail="Password requires " + ", ".join(errors))
    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(password)
    user.password_changed_at = now
    user.password_expires_at = (
        now + timedelta(days=settings.password_expiration_days)
        if settings.password_expiration_days > 0
        else None
    )
    user.status = "active"
    user.is_active = True


def password_is_expired(user: User) -> bool:
    if not user.password_expires_at:
        return False
    expiry = user.password_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry <= datetime.now(timezone.utc)


def create_password_reset_token(db: Session, user: User, hours: int = 24) -> str:
    now = datetime.now(timezone.utc)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.tenant_id == user.tenant_id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            tenant_id=user.tenant_id,
            token_hash=token_hash,
            expires_at=now + timedelta(hours=hours),
        )
    )
    return raw_token
