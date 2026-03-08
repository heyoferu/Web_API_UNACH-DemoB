import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate, UserRole
from tests.utils.admin_user import create_random_admin_user
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string, random_username

# ---------------------------------------------------------------------------
# List admin users
# ---------------------------------------------------------------------------


def test_read_admin_users_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_admin_user(db)
    r = client.get(
        f"{settings.API_V1_STR}/admin-users/",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    assert len(data["data"]) >= 1


def test_read_admin_users_as_admin(client: TestClient, db: Session) -> None:
    """Admins can list admin user profiles."""
    user, _ = create_random_admin_user(db)
    # Set a known password so we can authenticate
    password = random_lower_string()
    from app.models import UserUpdate

    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=password))
    headers = user_authentication_headers(
        client=client, email=user.email, password=password
    )
    r = client.get(
        f"{settings.API_V1_STR}/admin-users/",
        headers=headers,
    )
    assert r.status_code == 200


def test_read_admin_users_as_facilitator_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/admin-users/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Create admin user
# ---------------------------------------------------------------------------


def test_create_admin_user_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    # Create a user with admin role
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
        role=UserRole.admin,
    )
    user = crud.create_user(session=db, user_create=user_in)
    r = client.post(
        f"{settings.API_V1_STR}/admin-users/",
        headers=superuser_token_headers,
        json={
            "user_id": str(user.id),
            "admin_role": "application_approver",
            "department": "Aprobaciones",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["admin_role"] == "application_approver"
    assert data["department"] == "Aprobaciones"
    assert data["user_id"] == str(user.id)


def test_create_admin_user_as_admin_forbidden(client: TestClient, db: Session) -> None:
    """Only superusers can create admin profiles."""
    password = random_lower_string()
    user_in = UserCreate(
        email=random_email(),
        password=password,
        username=random_username(),
        role=UserRole.admin,
    )
    admin_user = crud.create_user(session=db, user_create=user_in)
    headers = user_authentication_headers(
        client=client, email=admin_user.email, password=password
    )
    # Try to create an admin profile for another user
    target_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
        role=UserRole.admin,
    )
    target = crud.create_user(session=db, user_create=target_in)
    r = client.post(
        f"{settings.API_V1_STR}/admin-users/",
        headers=headers,
        json={
            "user_id": str(target.id),
            "admin_role": "document_validator",
        },
    )
    assert r.status_code == 403


def test_create_admin_user_user_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/admin-users/",
        headers=superuser_token_headers,
        json={
            "user_id": str(uuid.uuid4()),
            "admin_role": "document_validator",
        },
    )
    assert r.status_code == 404


def test_create_admin_user_wrong_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Target user must have the admin role."""
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
        role=UserRole.facilitator,
    )
    user = crud.create_user(session=db, user_create=user_in)
    r = client.post(
        f"{settings.API_V1_STR}/admin-users/",
        headers=superuser_token_headers,
        json={
            "user_id": str(user.id),
            "admin_role": "document_validator",
        },
    )
    assert r.status_code == 400


def test_create_admin_user_duplicate(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user, _ = create_random_admin_user(db)
    r = client.post(
        f"{settings.API_V1_STR}/admin-users/",
        headers=superuser_token_headers,
        json={
            "user_id": str(user.id),
            "admin_role": "document_validator",
        },
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Read admin user by ID
# ---------------------------------------------------------------------------


def test_read_admin_user_by_id(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    _, admin_user = create_random_admin_user(db)
    r = client.get(
        f"{settings.API_V1_STR}/admin-users/{admin_user.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(admin_user.id)


def test_read_admin_user_by_id_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/admin-users/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Update admin user
# ---------------------------------------------------------------------------


def test_update_admin_user_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    _, admin_user = create_random_admin_user(db)
    r = client.patch(
        f"{settings.API_V1_STR}/admin-users/{admin_user.id}",
        headers=superuser_token_headers,
        json={"admin_role": "system_administrator", "department": "IT"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["admin_role"] == "system_administrator"
    assert data["department"] == "IT"


def test_update_admin_user_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.patch(
        f"{settings.API_V1_STR}/admin-users/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"department": "x"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete admin user
# ---------------------------------------------------------------------------


def test_delete_admin_user_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    _, admin_user = create_random_admin_user(db)
    r = client.delete(
        f"{settings.API_V1_STR}/admin-users/{admin_user.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Admin user profile deleted successfully"


def test_delete_admin_user_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/admin-users/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
