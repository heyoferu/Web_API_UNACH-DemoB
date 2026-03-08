import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    ApplicationStatus,
    ApplicationStatusHistoryCreate,
    FacilitatorCreate,
    UserCreate,
    UserRole,
)
from tests.utils.application import create_random_application
from tests.utils.beneficiary import create_random_beneficiary
from tests.utils.facilitator import create_random_facilitator
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string, random_username

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _facilitator_headers(
    client: TestClient, db: Session
) -> tuple[dict[str, str], "object", "object"]:
    """Create a facilitator + beneficiary and return (headers, facilitator, beneficiary)."""
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
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    headers = user_authentication_headers(client=client, email=email, password=password)
    return headers, facilitator, beneficiary


# ---------------------------------------------------------------------------
# Tests — List
# ---------------------------------------------------------------------------


def test_read_applications_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can list all applications."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    create_random_application(db, beneficiary=beneficiary)
    create_random_application(db, beneficiary=beneficiary)

    r = client.get(
        f"{settings.API_V1_STR}/applications/",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert "count" in data
    assert data["count"] >= 2


def test_read_applications_as_facilitator_own_only(
    client: TestClient, db: Session
) -> None:
    """Facilitator sees only applications for their own beneficiaries."""
    headers_a, _, beneficiary_a = _facilitator_headers(client, db)
    _, facilitator_b = create_random_facilitator(db)
    beneficiary_b = create_random_beneficiary(db, facilitator=facilitator_b)

    create_random_application(db, beneficiary=beneficiary_a)
    create_random_application(db, beneficiary=beneficiary_a)
    create_random_application(db, beneficiary=beneficiary_b)

    r = client.get(
        f"{settings.API_V1_STR}/applications/",
        headers=headers_a,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    for app_data in data["data"]:
        assert app_data["beneficiary_id"] == str(beneficiary_a.id)


# ---------------------------------------------------------------------------
# Tests — Create
# ---------------------------------------------------------------------------


def test_create_application_as_facilitator(client: TestClient, db: Session) -> None:
    """Facilitator can create an application for their own beneficiary."""
    headers, _, beneficiary = _facilitator_headers(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/applications/",
        headers=headers,
        json={
            "program_name": "Programa Test",
            "description": "Test desc",
            "beneficiary_id": str(beneficiary.id),
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["program_name"] == "Programa Test"
    assert data["status"] == "draft"
    assert data["beneficiary_id"] == str(beneficiary.id)


def test_create_application_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can create an application for any beneficiary."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)

    r = client.post(
        f"{settings.API_V1_STR}/applications/",
        headers=superuser_token_headers,
        json={
            "program_name": "Programa SU",
            "beneficiary_id": str(beneficiary.id),
        },
    )
    assert r.status_code == 200
    assert r.json()["program_name"] == "Programa SU"


def test_create_application_facilitator_other_beneficiary_forbidden(
    client: TestClient, db: Session
) -> None:
    """Facilitator cannot create an application for another facilitator's beneficiary."""
    headers_a, _, _ = _facilitator_headers(client, db)
    _, facilitator_b = create_random_facilitator(db)
    beneficiary_b = create_random_beneficiary(db, facilitator=facilitator_b)

    r = client.post(
        f"{settings.API_V1_STR}/applications/",
        headers=headers_a,
        json={
            "program_name": "Forbidden",
            "beneficiary_id": str(beneficiary_b.id),
        },
    )
    assert r.status_code == 403


def test_create_application_beneficiary_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Creating an application for a non-existent beneficiary returns 404."""
    r = client.post(
        f"{settings.API_V1_STR}/applications/",
        headers=superuser_token_headers,
        json={
            "program_name": "Test",
            "beneficiary_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Read by ID
# ---------------------------------------------------------------------------


def test_read_application_by_id(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Read an application by its ID."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)

    r = client.get(
        f"{settings.API_V1_STR}/applications/{application.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(application.id)


def test_read_application_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/applications/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


def test_read_application_other_facilitator_forbidden(
    client: TestClient, db: Session
) -> None:
    """Facilitator cannot read another facilitator's application."""
    headers_a, _, _ = _facilitator_headers(client, db)
    _, facilitator_b = create_random_facilitator(db)
    beneficiary_b = create_random_beneficiary(db, facilitator=facilitator_b)
    application_b = create_random_application(db, beneficiary=beneficiary_b)

    r = client.get(
        f"{settings.API_V1_STR}/applications/{application_b.id}",
        headers=headers_a,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Tests — Update
# ---------------------------------------------------------------------------


def test_update_application_draft(client: TestClient, db: Session) -> None:
    """Facilitator can update a draft application."""
    headers, _, beneficiary = _facilitator_headers(client, db)
    application = create_random_application(db, beneficiary=beneficiary)

    r = client.patch(
        f"{settings.API_V1_STR}/applications/{application.id}",
        headers=headers,
        json={"program_name": "Updated Name"},
    )
    assert r.status_code == 200
    assert r.json()["program_name"] == "Updated Name"


def test_update_application_non_draft_fails(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Cannot update a non-draft application."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)

    # Move to submitted
    crud.create_status_history(
        session=db,
        application=application,
        history_in=ApplicationStatusHistoryCreate(
            new_status=ApplicationStatus.submitted
        ),
    )

    r = client.patch(
        f"{settings.API_V1_STR}/applications/{application.id}",
        headers=superuser_token_headers,
        json={"program_name": "Should Fail"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Tests — Delete
# ---------------------------------------------------------------------------


def test_delete_application_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can delete an application."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)

    r = client.delete(
        f"{settings.API_V1_STR}/applications/{application.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Application deleted successfully"


def test_delete_application_as_facilitator_forbidden(
    client: TestClient, db: Session
) -> None:
    """Facilitators cannot delete applications (admin/superuser only)."""
    headers, _, beneficiary = _facilitator_headers(client, db)
    application = create_random_application(db, beneficiary=beneficiary)

    r = client.delete(
        f"{settings.API_V1_STR}/applications/{application.id}",
        headers=headers,
    )
    assert r.status_code == 403


def test_delete_application_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/applications/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Status Transition
# ---------------------------------------------------------------------------


def test_transition_draft_to_submitted(client: TestClient, db: Session) -> None:
    """Facilitator can submit a draft application."""
    headers, _, beneficiary = _facilitator_headers(client, db)
    application = create_random_application(db, beneficiary=beneficiary)

    r = client.post(
        f"{settings.API_V1_STR}/applications/{application.id}/status",
        headers=headers,
        json={"new_status": "submitted", "comment": "Ready for review"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["previous_status"] == "draft"
    assert data["new_status"] == "submitted"
    assert data["comment"] == "Ready for review"


def test_transition_invalid(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Invalid status transition returns 400."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)

    # draft → approved is not valid
    r = client.post(
        f"{settings.API_V1_STR}/applications/{application.id}/status",
        headers=superuser_token_headers,
        json={"new_status": "approved"},
    )
    assert r.status_code == 400


def test_facilitator_cannot_approve(client: TestClient, db: Session) -> None:
    """Facilitator cannot perform review transitions (approve/reject/under_review)."""
    headers, _, beneficiary = _facilitator_headers(client, db)
    application = create_random_application(db, beneficiary=beneficiary)

    # Submit first
    client.post(
        f"{settings.API_V1_STR}/applications/{application.id}/status",
        headers=headers,
        json={"new_status": "submitted"},
    )

    # Facilitator tries to move to under_review — should be denied
    r = client.post(
        f"{settings.API_V1_STR}/applications/{application.id}/status",
        headers=headers,
        json={"new_status": "under_review"},
    )
    assert r.status_code == 403


def test_superuser_full_lifecycle(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can drive the full lifecycle: draft → submitted → under_review → approved."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)
    app_id = str(application.id)
    url = f"{settings.API_V1_STR}/applications/{app_id}/status"

    for new_status in ("submitted", "under_review", "approved"):
        r = client.post(
            url,
            headers=superuser_token_headers,
            json={"new_status": new_status},
        )
        assert r.status_code == 200, f"Failed to transition to {new_status}: {r.json()}"

    # Verify application is now approved
    r = client.get(
        f"{settings.API_V1_STR}/applications/{app_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Tests — Status History Listing
# ---------------------------------------------------------------------------


def test_read_status_history(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Read the status history for an application."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)
    app_id = str(application.id)
    url = f"{settings.API_V1_STR}/applications/{app_id}/status"

    # Make some transitions
    client.post(url, headers=superuser_token_headers, json={"new_status": "submitted"})
    client.post(
        url, headers=superuser_token_headers, json={"new_status": "under_review"}
    )

    r = client.get(
        f"{settings.API_V1_STR}/applications/{app_id}/status-history",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    assert len(data["data"]) == 2
