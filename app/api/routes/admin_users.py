import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_admin_or_superuser
from app.core.config import settings
from app.core.totp import (
    generate_totp_secret,
    get_totp_provisioning_uri,
    verify_totp_code,
)
from app.models import (
    AdminUser,
    AdminUserCreate,
    AdminUserPublic,
    AdminUsersPublic,
    AdminUserUpdate,
    Message,
    MfaSetupResponse,
    MfaVerifyRequest,
    User,
    UserRole,
)

router = APIRouter(
    prefix="/admin-users",
    tags=["admin-users"],
    dependencies=[Depends(get_current_admin_or_superuser)],
)


# ---------------------------------------------------------------------------
# MFA management endpoints
# ---------------------------------------------------------------------------


@router.post("/me/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(*, session: SessionDep, current_user: CurrentUser) -> Any:
    """Initiate MFA setup for the current admin user.

    Generates a TOTP secret and returns the provisioning URI (for QR code)
    and the base32 secret.  The secret is stored but MFA is **not** enabled
    until the user confirms with ``POST /me/mfa/verify-setup``.
    """
    statement = select(AdminUser).where(AdminUser.user_id == current_user.id)
    admin_user = session.exec(statement).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user profile not found")

    if admin_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    secret = generate_totp_secret()
    admin_user.mfa_secret = secret
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    provisioning_uri = get_totp_provisioning_uri(
        secret=secret,
        email=current_user.email,
        issuer=settings.MFA_ISSUER,
    )
    return MfaSetupResponse(secret=secret, provisioning_uri=provisioning_uri)


@router.post("/me/mfa/verify-setup")
def mfa_verify_setup(
    *, session: SessionDep, current_user: CurrentUser, body: MfaVerifyRequest
) -> Message:
    """Confirm MFA setup by verifying a TOTP code.

    After this endpoint returns successfully, MFA is enabled and the user
    will be required to provide a TOTP code on every login.
    """
    statement = select(AdminUser).where(AdminUser.user_id == current_user.id)
    admin_user = session.exec(statement).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user profile not found")

    if admin_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    if not admin_user.mfa_secret:
        raise HTTPException(
            status_code=400,
            detail="MFA setup not initiated. Call POST /me/mfa/setup first.",
        )

    if not verify_totp_code(secret=admin_user.mfa_secret, code=body.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    admin_user.mfa_enabled = True
    session.add(admin_user)
    session.commit()
    return Message(message="MFA enabled successfully")


@router.delete("/me/mfa")
def mfa_disable(
    *, session: SessionDep, current_user: CurrentUser, body: MfaVerifyRequest
) -> Message:
    """Disable MFA for the current admin user.

    Requires a valid TOTP code for confirmation.
    """
    statement = select(AdminUser).where(AdminUser.user_id == current_user.id)
    admin_user = session.exec(statement).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user profile not found")

    if not admin_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is not enabled")

    if not admin_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA secret not found")

    if not verify_totp_code(secret=admin_user.mfa_secret, code=body.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    admin_user.mfa_enabled = False
    admin_user.mfa_secret = None
    session.add(admin_user)
    session.commit()
    return Message(message="MFA disabled successfully")


# ---------------------------------------------------------------------------
# Admin user CRUD endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=AdminUsersPublic)
def read_admin_users(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Retrieve admin user profiles."""
    count_statement = select(func.count()).select_from(AdminUser)
    count = session.exec(count_statement).one()
    statement = select(AdminUser).offset(skip).limit(limit)
    admin_users = session.exec(statement).all()
    return AdminUsersPublic(data=admin_users, count=count)


@router.post("/", response_model=AdminUserPublic)
def create_admin_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    admin_user_in: AdminUserCreate,
) -> Any:
    """Create a new admin user profile.

    The target user must exist and have the admin role.
    Only superusers can create admin profiles.
    """
    if current_user.role != UserRole.superuser:
        raise HTTPException(
            status_code=403,
            detail="Only superusers can create admin user profiles",
        )

    user = session.get(User, admin_user_in.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=400,
            detail="Target user must have the admin role",
        )

    existing = crud.get_admin_user_by_user_id(
        session=session, user_id=admin_user_in.user_id
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Admin user profile already exists for this user",
        )

    admin_user = crud.create_admin_user(session=session, admin_user_in=admin_user_in)
    return admin_user


@router.get("/{admin_user_id}", response_model=AdminUserPublic)
def read_admin_user_by_id(
    admin_user_id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """Get a specific admin user profile by id."""
    admin_user = session.get(AdminUser, admin_user_id)
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user profile not found")
    return admin_user


@router.patch("/{admin_user_id}", response_model=AdminUserPublic)
def update_admin_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    admin_user_id: uuid.UUID,
    admin_user_in: AdminUserUpdate,
) -> Any:
    """Update an admin user profile.

    Only superusers can update admin profiles.
    """
    if current_user.role != UserRole.superuser:
        raise HTTPException(
            status_code=403,
            detail="Only superusers can update admin user profiles",
        )

    admin_user = session.get(AdminUser, admin_user_id)
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user profile not found")

    admin_user = crud.update_admin_user(
        session=session, db_admin_user=admin_user, admin_user_in=admin_user_in
    )
    return admin_user


@router.delete("/{admin_user_id}")
def delete_admin_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    admin_user_id: uuid.UUID,
) -> Message:
    """Delete an admin user profile.

    Only superusers can delete admin profiles.
    """
    if current_user.role != UserRole.superuser:
        raise HTTPException(
            status_code=403,
            detail="Only superusers can delete admin user profiles",
        )

    admin_user = session.get(AdminUser, admin_user_id)
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user profile not found")

    session.delete(admin_user)
    session.commit()
    return Message(message="Admin user profile deleted successfully")
