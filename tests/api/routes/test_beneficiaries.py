from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import FacilitatorCreate, UserCreate, UserRole
from tests.utils.beneficiary import create_random_beneficiary, random_curp
from tests.utils.facilitator import create_random_facilitator
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string, random_username

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _facilitator_headers(
    client: TestClient, db: Session
) -> tuple[dict[str, str], "object"]:
    """Create a facilitator user + profile and return (auth_headers, facilitator)."""
    email = random_email()
    password = random_lower_string()
    username = random_username()
    user_in = UserCreate(
        email=email, password=password, username=username, role=UserRole.facilitator
    )
    user = crud.create_user(session=db, user_create=user_in)
    facilitator = crud.create_facilitator(
        session=db,
        facilitator_in=FacilitatorCreate(user_id=user.id, phone="+520000000000"),
    )
    headers = user_authentication_headers(client=client, email=email, password=password)
    return headers, facilitator


# ---------------------------------------------------------------------------
# Tests — List
# ---------------------------------------------------------------------------


def test_read_beneficiaries_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can list all beneficiaries."""
    _, facilitator = create_random_facilitator(db)
    create_random_beneficiary(db, facilitator=facilitator)
    create_random_beneficiary(db, facilitator=facilitator)

    r = client.get(
        f"{settings.API_V1_STR}/beneficiaries/",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert "count" in data
    assert data["count"] >= 2


def test_read_beneficiaries_as_facilitator_own_only(
    client: TestClient, db: Session
) -> None:
    """Facilitator sees only their own beneficiaries."""
    headers_a, facilitator_a = _facilitator_headers(client, db)
    _, facilitator_b = create_random_facilitator(db)

    create_random_beneficiary(db, facilitator=facilitator_a)
    create_random_beneficiary(db, facilitator=facilitator_a)
    create_random_beneficiary(db, facilitator=facilitator_b)

    r = client.get(
        f"{settings.API_V1_STR}/beneficiaries/",
        headers=headers_a,
    )
    assert r.status_code == 200
    data = r.json()
    # Should only see the 2 belonging to facilitator_a
    assert data["count"] == 2
    for b in data["data"]:
        assert b["facilitator_id"] == str(facilitator_a.id)


# ---------------------------------------------------------------------------
# Tests — Create
# ---------------------------------------------------------------------------


def test_create_beneficiary_as_facilitator(client: TestClient, db: Session) -> None:
    """Facilitator can create a beneficiary for themselves."""
    headers, facilitator = _facilitator_headers(client, db)
    curp = random_curp()

    r = client.post(
        f"{settings.API_V1_STR}/beneficiaries/",
        headers=headers,
        json={
            "curp": curp,
            "full_name": "Ana García",
            "facilitator_id": str(facilitator.id),
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["curp"] == curp
    assert data["full_name"] == "Ana García"
    assert data["facilitator_id"] == str(facilitator.id)


def test_create_beneficiary_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can create a beneficiary for any facilitator."""
    _, facilitator = create_random_facilitator(db)
    curp = random_curp()

    r = client.post(
        f"{settings.API_V1_STR}/beneficiaries/",
        headers=superuser_token_headers,
        json={
            "curp": curp,
            "full_name": "Pedro Test",
            "facilitator_id": str(facilitator.id),
        },
    )
    assert r.status_code == 200
    assert r.json()["curp"] == curp


def test_create_beneficiary_facilitator_cannot_assign_other(
    client: TestClient, db: Session
) -> None:
    """Facilitator cannot create a beneficiary for another facilitator."""
    headers_a, _ = _facilitator_headers(client, db)
    _, facilitator_b = create_random_facilitator(db)

    r = client.post(
        f"{settings.API_V1_STR}/beneficiaries/",
        headers=headers_a,
        json={
            "curp": random_curp(),
            "full_name": "Forbidden Test",
            "facilitator_id": str(facilitator_b.id),
        },
    )
    assert r.status_code == 403


def test_create_beneficiary_duplicate_curp(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Duplicate CURP returns 409."""
    _, facilitator = create_random_facilitator(db)
    curp = random_curp()

    # First creation succeeds
    r = client.post(
        f"{settings.API_V1_STR}/beneficiaries/",
        headers=superuser_token_headers,
        json={
            "curp": curp,
            "full_name": "First",
            "facilitator_id": str(facilitator.id),
        },
    )
    assert r.status_code == 200

    # Second creation with same CURP fails
    r = client.post(
        f"{settings.API_V1_STR}/beneficiaries/",
        headers=superuser_token_headers,
        json={
            "curp": curp,
            "full_name": "Second",
            "facilitator_id": str(facilitator.id),
        },
    )
    assert r.status_code == 409


def test_create_beneficiary_facilitator_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Creating a beneficiary for a non-existent facilitator returns 404."""
    import uuid

    r = client.post(
        f"{settings.API_V1_STR}/beneficiaries/",
        headers=superuser_token_headers,
        json={
            "curp": random_curp(),
            "full_name": "Nobody",
            "facilitator_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Read by ID
# ---------------------------------------------------------------------------


def test_read_beneficiary_by_id_as_facilitator(client: TestClient, db: Session) -> None:
    """Facilitator can read their own beneficiary."""
    headers, facilitator = _facilitator_headers(client, db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)

    r = client.get(
        f"{settings.API_V1_STR}/beneficiaries/{beneficiary.id}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(beneficiary.id)


def test_read_beneficiary_by_id_other_facilitator_forbidden(
    client: TestClient, db: Session
) -> None:
    """Facilitator cannot read another facilitator's beneficiary."""
    headers_a, _ = _facilitator_headers(client, db)
    _, facilitator_b = create_random_facilitator(db)
    beneficiary_b = create_random_beneficiary(db, facilitator=facilitator_b)

    r = client.get(
        f"{settings.API_V1_STR}/beneficiaries/{beneficiary_b.id}",
        headers=headers_a,
    )
    assert r.status_code == 403


def test_read_beneficiary_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    import uuid

    r = client.get(
        f"{settings.API_V1_STR}/beneficiaries/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Update
# ---------------------------------------------------------------------------


def test_update_beneficiary_as_facilitator(client: TestClient, db: Session) -> None:
    """Facilitator can update their own beneficiary."""
    headers, facilitator = _facilitator_headers(client, db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)

    r = client.patch(
        f"{settings.API_V1_STR}/beneficiaries/{beneficiary.id}",
        headers=headers,
        json={"community": "New Community"},
    )
    assert r.status_code == 200
    assert r.json()["community"] == "New Community"


def test_update_beneficiary_other_facilitator_forbidden(
    client: TestClient, db: Session
) -> None:
    """Facilitator cannot update another facilitator's beneficiary."""
    headers_a, _ = _facilitator_headers(client, db)
    _, facilitator_b = create_random_facilitator(db)
    beneficiary_b = create_random_beneficiary(db, facilitator=facilitator_b)

    r = client.patch(
        f"{settings.API_V1_STR}/beneficiaries/{beneficiary_b.id}",
        headers=headers_a,
        json={"community": "Hacked"},
    )
    assert r.status_code == 403


def test_update_beneficiary_duplicate_curp(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Changing CURP to an already-used one returns 409."""
    _, facilitator = create_random_facilitator(db)
    b1 = create_random_beneficiary(db, facilitator=facilitator)
    b2 = create_random_beneficiary(db, facilitator=facilitator)

    r = client.patch(
        f"{settings.API_V1_STR}/beneficiaries/{b2.id}",
        headers=superuser_token_headers,
        json={"curp": b1.curp},
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Tests — Delete
# ---------------------------------------------------------------------------


def test_delete_beneficiary_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can delete a beneficiary."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)

    r = client.delete(
        f"{settings.API_V1_STR}/beneficiaries/{beneficiary.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Beneficiary deleted successfully"


def test_delete_beneficiary_as_facilitator_forbidden(
    client: TestClient, db: Session
) -> None:
    """Facilitators cannot delete beneficiaries (admin/superuser only)."""
    headers, facilitator = _facilitator_headers(client, db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)

    r = client.delete(
        f"{settings.API_V1_STR}/beneficiaries/{beneficiary.id}",
        headers=headers,
    )
    assert r.status_code == 403


def test_delete_beneficiary_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    import uuid

    r = client.delete(
        f"{settings.API_V1_STR}/beneficiaries/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
