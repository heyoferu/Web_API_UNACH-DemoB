from sqlmodel import Session

from app import crud
from app.models import (
    AdminRole,
    AdminUser,
    AdminUserCreate,
    User,
    UserCreate,
    UserRole,
)
from tests.utils.utils import random_email, random_lower_string, random_username


def create_random_admin_user(
    db: Session,
    *,
    admin_role: AdminRole = AdminRole.document_validator,
) -> tuple[User, AdminUser]:
    """Create a random user with admin role and an admin user profile.

    Returns a (user, admin_user) tuple.
    """
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email,
        password=password,
        username=username,
        role=UserRole.admin,
    )
    user = crud.create_user(session=db, user_create=user_in)
    admin_user_in = AdminUserCreate(
        user_id=user.id,
        admin_role=admin_role,
        department="Test Department",
    )
    admin_user = crud.create_admin_user(session=db, admin_user_in=admin_user_in)
    return user, admin_user
