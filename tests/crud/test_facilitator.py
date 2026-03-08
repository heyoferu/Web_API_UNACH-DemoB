from sqlmodel import Session

from app import crud
from app.models import (
    FacilitatorCreate,
    FacilitatorUpdate,
    UserCreate,
    UserRole,
)
from tests.utils.utils import random_email, random_lower_string, random_username


def test_create_facilitator(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.facilitator
    )
    user = crud.create_user(session=db, user_create=user_in)

    facilitator_in = FacilitatorCreate(
        user_id=user.id, phone="+521234567890", zone="Sur", organization="Org A"
    )
    facilitator = crud.create_facilitator(session=db, facilitator_in=facilitator_in)

    assert facilitator.user_id == user.id
    assert facilitator.phone == "+521234567890"
    assert facilitator.zone == "Sur"
    assert facilitator.organization == "Org A"
    assert facilitator.id is not None
    assert facilitator.created_at is not None


def test_update_facilitator(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.facilitator
    )
    user = crud.create_user(session=db, user_create=user_in)

    facilitator_in = FacilitatorCreate(user_id=user.id, phone="+521111111111")
    facilitator = crud.create_facilitator(session=db, facilitator_in=facilitator_in)

    update_data = FacilitatorUpdate(phone="+529999999999", zone="Este")
    updated = crud.update_facilitator(
        session=db, db_facilitator=facilitator, facilitator_in=update_data
    )

    assert updated.phone == "+529999999999"
    assert updated.zone == "Este"
    assert updated.id == facilitator.id


def test_get_facilitator_by_user_id(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.facilitator
    )
    user = crud.create_user(session=db, user_create=user_in)

    facilitator_in = FacilitatorCreate(user_id=user.id, phone="+520000000000")
    created = crud.create_facilitator(session=db, facilitator_in=facilitator_in)

    found = crud.get_facilitator_by_user_id(session=db, user_id=user.id)
    assert found is not None
    assert found.id == created.id


def test_get_facilitator_by_user_id_not_found(db: Session) -> None:
    import uuid

    result = crud.get_facilitator_by_user_id(session=db, user_id=uuid.uuid4())
    assert result is None
