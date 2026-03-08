from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate, UserRole
from tests.utils.facilitator import create_random_facilitator
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string, random_username


def test_read_facilitators_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can list all facilitators."""
    create_random_facilitator(db)
    create_random_facilitator(db)

    r = client.get(
        f"{settings.API_V1_STR}/facilitators/",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert "count" in data
    assert data["count"] >= 2


def test_read_facilitators_as_normal_user_forbidden(
    client: TestClient, db: Session
) -> None:
    """Facilitator role users cannot list all facilitators."""
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.facilitator
    )
    crud.create_user(session=db, user_create=user_in)
    headers = user_authentication_headers(client=client, email=email, password=password)

    r = client.get(f"{settings.API_V1_STR}/facilitators/", headers=headers)
    assert r.status_code == 403


def test_create_facilitator_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can create a facilitator profile for a user with facilitator role."""
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.facilitator
    )
    user = crud.create_user(session=db, user_create=user_in)

    r = client.post(
        f"{settings.API_V1_STR}/facilitators/",
        headers=superuser_token_headers,
        json={
            "user_id": str(user.id),
            "phone": "+521234567890",
            "zone": "Norte",
            "organization": "Test Org",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == str(user.id)
    assert data["phone"] == "+521234567890"
    assert data["zone"] == "Norte"


def test_create_facilitator_user_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Creating a facilitator for a non-existent user returns 404."""
    import uuid

    r = client.post(
        f"{settings.API_V1_STR}/facilitators/",
        headers=superuser_token_headers,
        json={"user_id": str(uuid.uuid4()), "phone": "+520000000000"},
    )
    assert r.status_code == 404


def test_create_facilitator_wrong_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Creating a facilitator for a user that is not a facilitator returns 400."""
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.admin
    )
    user = crud.create_user(session=db, user_create=user_in)

    r = client.post(
        f"{settings.API_V1_STR}/facilitators/",
        headers=superuser_token_headers,
        json={"user_id": str(user.id)},
    )
    assert r.status_code == 400
    assert "facilitator role" in r.json()["detail"]


def test_create_facilitator_duplicate(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Creating a second facilitator profile for the same user returns 409."""
    user, _ = create_random_facilitator(db)

    r = client.post(
        f"{settings.API_V1_STR}/facilitators/",
        headers=superuser_token_headers,
        json={"user_id": str(user.id)},
    )
    assert r.status_code == 409


def test_read_facilitator_me(client: TestClient, db: Session) -> None:
    """Facilitator can read their own profile via /me."""
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.facilitator
    )
    user = crud.create_user(session=db, user_create=user_in)
    from app.models import FacilitatorCreate

    crud.create_facilitator(
        session=db,
        facilitator_in=FacilitatorCreate(user_id=user.id, phone="+520000000000"),
    )
    headers = user_authentication_headers(client=client, email=email, password=password)

    r = client.get(f"{settings.API_V1_STR}/facilitators/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["user_id"] == str(user.id)


def test_read_facilitator_me_no_profile(client: TestClient, db: Session) -> None:
    """Facilitator without a profile gets 404 on /me."""
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.facilitator
    )
    crud.create_user(session=db, user_create=user_in)
    headers = user_authentication_headers(client=client, email=email, password=password)

    r = client.get(f"{settings.API_V1_STR}/facilitators/me", headers=headers)
    assert r.status_code == 404


def test_read_facilitator_me_wrong_role(client: TestClient, db: Session) -> None:
    """Non-facilitator user gets 400 on /me."""
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.admin
    )
    crud.create_user(session=db, user_create=user_in)
    headers = user_authentication_headers(client=client, email=email, password=password)

    r = client.get(f"{settings.API_V1_STR}/facilitators/me", headers=headers)
    assert r.status_code == 400


def test_update_facilitator_me(client: TestClient, db: Session) -> None:
    """Facilitator can update their own profile via PATCH /me."""
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.facilitator
    )
    user = crud.create_user(session=db, user_create=user_in)
    from app.models import FacilitatorCreate

    crud.create_facilitator(
        session=db,
        facilitator_in=FacilitatorCreate(user_id=user.id, zone="Oeste"),
    )
    headers = user_authentication_headers(client=client, email=email, password=password)

    r = client.patch(
        f"{settings.API_V1_STR}/facilitators/me",
        headers=headers,
        json={"zone": "Este", "organization": "Updated Org"},
    )
    assert r.status_code == 200
    assert r.json()["zone"] == "Este"
    assert r.json()["organization"] == "Updated Org"


def test_read_facilitator_by_id_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can read a facilitator by id."""
    _, facilitator = create_random_facilitator(db)

    r = client.get(
        f"{settings.API_V1_STR}/facilitators/{facilitator.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(facilitator.id)


def test_read_facilitator_by_id_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    import uuid

    r = client.get(
        f"{settings.API_V1_STR}/facilitators/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


def test_update_facilitator_by_id(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can update a facilitator by id."""
    _, facilitator = create_random_facilitator(db)

    r = client.patch(
        f"{settings.API_V1_STR}/facilitators/{facilitator.id}",
        headers=superuser_token_headers,
        json={"phone": "+529876543210"},
    )
    assert r.status_code == 200
    assert r.json()["phone"] == "+529876543210"


def test_delete_facilitator(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can delete a facilitator."""
    _, facilitator = create_random_facilitator(db)

    r = client.delete(
        f"{settings.API_V1_STR}/facilitators/{facilitator.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Facilitator deleted successfully"

    # Verify it's gone
    r = client.get(
        f"{settings.API_V1_STR}/facilitators/{facilitator.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


def test_delete_facilitator_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    import uuid

    r = client.delete(
        f"{settings.API_V1_STR}/facilitators/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
