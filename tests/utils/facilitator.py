from sqlmodel import Session

from app import crud
from app.models import (
    Facilitator,
    FacilitatorCreate,
    User,
    UserCreate,
    UserRole,
)
from tests.utils.utils import random_email, random_lower_string, random_username


def create_random_facilitator(db: Session) -> tuple[User, Facilitator]:
    """Create a random user with facilitator role and a facilitator profile.

    Returns a (user, facilitator) tuple.
    """
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email,
        password=password,
        username=username,
        role=UserRole.facilitator,
    )
    user = crud.create_user(session=db, user_create=user_in)
    facilitator_in = FacilitatorCreate(
        user_id=user.id,
        phone="+5200000000000",
        zone="Norte",
        organization="ONG Test",
    )
    facilitator = crud.create_facilitator(session=db, facilitator_in=facilitator_in)
    return user, facilitator
