from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import hashlib
from datetime import datetime, timezone

from app.models import PasswordResetToken, Role, User
from app.schemas.auth import CurrentUser, PasswordChangeRequest, PasswordResetRequest, TokenRequest, TokenResponse
from app.services.auth import (
    AUTH_MODE,
    create_access_token,
    current_user_from_model,
    get_auth_db,
    get_current_user,
    ensure_tenant_settings,
    password_is_expired,
    set_local_password,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def issue_local_token(request: TokenRequest, db: Session = Depends(get_auth_db)):
    if AUTH_MODE not in {"local", "hybrid"}:
        raise HTTPException(status_code=404, detail="Local authentication is disabled")
    user = db.query(User).filter(
        User.email == request.email.lower(),
        User.tenant_id == request.tenant_id,
    ).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if user.auth_source != "local":
        raise HTTPException(status_code=409, detail="Use enterprise SSO for this account")
    if password_is_expired(user):
        user.status = "password_expired"
        user.is_active = False
        db.commit()
        raise HTTPException(status_code=403, detail="Password has expired. Use the reset link to reactivate the account")
    if not user.is_active or user.is_archived or user.status != "active":
        raise HTTPException(status_code=403, detail="User account is inactive")
    role = db.query(Role).filter(Role.id == user.role_id, Role.is_archived.is_(False)).first()
    if not role:
        raise HTTPException(status_code=403, detail="User has no active role")
    access_token, expires_in = create_access_token(user, role)
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=current_user_from_model(user, role),
    )


@router.get("/current-user", response_model=CurrentUser)
def read_current_user(user: CurrentUser = Depends(get_current_user)):
    return user


@router.post("/refresh", response_model=TokenResponse)
def refresh_local_token(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_auth_db),
):
    if current.auth_source != "local":
        raise HTTPException(status_code=409, detail="Enterprise SSO sessions refresh through the identity provider")
    user = db.query(User).filter(User.id == current.id).first()
    role = db.query(Role).filter(Role.id == user.role_id).first()
    access_token, expires_in = create_access_token(user, role)
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=current_user_from_model(user, role),
    )


@router.post("/reset-password")
def reset_local_password(request: PasswordResetRequest, db: Session = Depends(get_auth_db)):
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    reset = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
    ).first()
    if not reset:
        raise HTTPException(status_code=400, detail="Password reset link is invalid")
    expires_at = reset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Password reset link has expired")
    user = db.query(User).filter(User.id == reset.user_id, User.auth_source == "local").first()
    if not user:
        raise HTTPException(status_code=400, detail="Local user was not found")
    settings = ensure_tenant_settings(db, user.tenant_id)
    set_local_password(user, request.password, settings)
    reset.used_at = datetime.now(timezone.utc)
    user.onboarding_status = "complete"
    db.commit()
    return {"message": "Password updated. You can now sign in."}


@router.post("/change-password")
def change_local_password(
    request: PasswordChangeRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_auth_db),
):
    if current.auth_source != "local":
        raise HTTPException(status_code=409, detail="Password changes are managed by your identity provider")
    user = db.query(User).filter(User.id == current.id, User.tenant_id == current.tenant_id).first()
    if not user or not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    set_local_password(user, request.new_password, ensure_tenant_settings(db, current.tenant_id))
    user.onboarding_status = "complete"
    db.commit()
    return {"message": "Password updated successfully"}
