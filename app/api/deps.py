from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import AdminUser, TokenPayload, User, UserRole

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def _decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token, returning the payload."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    return token_data


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    token_data = _decode_token(token)
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    """Require the current user to have the superuser role."""
    if current_user.role != UserRole.superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def _check_mfa_verified(session: Session, token: str, user: User) -> None:
    """Raise 403 if the admin user has MFA enabled but the token lacks verification.

    Non-admin users and admin users without MFA enabled are allowed through.
    """
    if user.role not in (UserRole.admin, UserRole.superuser):
        return

    from sqlmodel import select

    statement = select(AdminUser).where(AdminUser.user_id == user.id)
    admin_user = session.exec(statement).first()
    if not admin_user or not admin_user.mfa_enabled:
        return

    # Admin has MFA enabled — check the token claim
    token_data = _decode_token(token)
    if not token_data.mfa_verified:
        raise HTTPException(
            status_code=403,
            detail="MFA verification required",
        )


def get_current_admin_or_superuser(
    session: SessionDep, current_user: CurrentUser, token: TokenDep
) -> User:
    """Require the current user to have at least admin role and MFA verified."""
    if current_user.role not in (UserRole.admin, UserRole.superuser):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    _check_mfa_verified(session, token, current_user)
    return current_user
