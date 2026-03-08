from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from sqlmodel import select

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security
from app.core.config import settings
from app.core.totp import verify_totp_code
from app.models import (
    AdminUser,
    Message,
    MfaLoginRequest,
    NewPassword,
    Token,
    TokenPayload,
    UserPublic,
    UserUpdate,
)
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """OAuth2 compatible token login, get an access token for future requests.

    If the user has MFA enabled, returns a short-lived token with
    ``mfa_verified=false``.  The client must then call
    ``POST /login/mfa-verify`` to exchange it for a full token.
    """
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Update last_login timestamp
    user.last_login = datetime.now(timezone.utc)
    session.add(user)
    session.commit()

    # Check whether the user has MFA enabled
    statement = select(AdminUser).where(AdminUser.user_id == user.id)
    admin_user = session.exec(statement).first()

    if admin_user and admin_user.mfa_enabled:
        # Return a short-lived MFA-pending token
        mfa_token_expires = timedelta(minutes=settings.MFA_TOKEN_EXPIRE_MINUTES)
        return Token(
            access_token=security.create_access_token(
                user.id,
                expires_delta=mfa_token_expires,
                mfa_verified=False,
            )
        )

    # No MFA — return a full access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post("/login/mfa-verify")
def login_mfa_verify(session: SessionDep, body: MfaLoginRequest) -> Token:
    """Verify a TOTP code and exchange an MFA-pending token for a full token.

    The ``mfa_token`` must be a valid JWT with ``mfa_verified=false``.
    """
    # Decode the MFA-pending token
    try:
        payload = jwt.decode(
            body.mfa_token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, Exception):
        raise HTTPException(status_code=400, detail="Invalid or expired MFA token")

    if token_data.mfa_verified:
        raise HTTPException(status_code=400, detail="Token is already MFA-verified")

    from app.models import User

    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired MFA token")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Look up admin user to get the TOTP secret
    statement = select(AdminUser).where(AdminUser.user_id == user.id)
    admin_user = session.exec(statement).first()
    if not admin_user or not admin_user.mfa_enabled or not admin_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not enabled for this user")

    if not verify_totp_code(secret=admin_user.mfa_secret, code=body.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # Issue a full access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires, mfa_verified=True
        )
    )


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """Test access token."""
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    """Password Recovery."""
    user = crud.get_user_by_email(session=session, email=email)

    # Always return the same response to prevent email enumeration attacks
    # Only send email if user actually exists
    if user:
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """Reset password."""
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = crud.get_user_by_email(session=session, email=email)
    if not user:
        # Don't reveal that the user doesn't exist - use same error as invalid token
        raise HTTPException(status_code=400, detail="Invalid token")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    user_in_update = UserUpdate(password=body.new_password)
    crud.update_user(
        session=session,
        db_user=user,
        user_in=user_in_update,
    )
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """HTML Content for Password Recovery."""
    user = crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
