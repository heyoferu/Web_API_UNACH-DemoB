import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    DocumentCreate,
    DocumentType,
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


def _setup_facilitator_with_app(
    client: TestClient, db: Session
) -> tuple[dict[str, str], "object", "object"]:
    """Create a facilitator + beneficiary + application. Return (headers, facilitator, application)."""
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
    application = create_random_application(db, beneficiary=beneficiary)
    headers = user_authentication_headers(client=client, email=email, password=password)
    return headers, facilitator, application


def _create_document_in_db(db: Session, application_id: uuid.UUID) -> "object":
    """Create a document directly in the DB."""
    doc_in = DocumentCreate(
        document_type=DocumentType.id_document,
        file_name="test.pdf",
        file_url="https://storage.example.com/test.pdf",
        description="Test document",
        application_id=application_id,
    )
    return crud.create_document(session=db, document_in=doc_in)


# ---------------------------------------------------------------------------
# Tests — List
# ---------------------------------------------------------------------------


def test_read_documents(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can list documents for an application."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)
    _create_document_in_db(db, application.id)
    _create_document_in_db(db, application.id)

    r = client.get(
        f"{settings.API_V1_STR}/documents/",
        headers=superuser_token_headers,
        params={"application_id": str(application.id)},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 2


def test_read_documents_application_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Listing documents for a non-existent application returns 404."""
    r = client.get(
        f"{settings.API_V1_STR}/documents/",
        headers=superuser_token_headers,
        params={"application_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


def test_read_documents_other_facilitator_forbidden(
    client: TestClient, db: Session
) -> None:
    """Facilitator cannot list documents for another facilitator's application."""
    headers_a, _, _ = _setup_facilitator_with_app(client, db)
    _, facilitator_b = create_random_facilitator(db)
    beneficiary_b = create_random_beneficiary(db, facilitator=facilitator_b)
    application_b = create_random_application(db, beneficiary=beneficiary_b)

    r = client.get(
        f"{settings.API_V1_STR}/documents/",
        headers=headers_a,
        params={"application_id": str(application_b.id)},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Tests — Create
# ---------------------------------------------------------------------------


def test_create_document_as_facilitator(client: TestClient, db: Session) -> None:
    """Facilitator can create a document for their own application."""
    headers, _, application = _setup_facilitator_with_app(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/documents/",
        headers=headers,
        json={
            "document_type": "proof_of_address",
            "file_name": "comprobante.pdf",
            "file_url": "https://storage.example.com/comprobante.pdf",
            "application_id": str(application.id),
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["document_type"] == "proof_of_address"
    assert data["file_name"] == "comprobante.pdf"
    assert data["uploaded_by"] is not None


def test_create_document_application_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Creating a document for a non-existent application returns 404."""
    r = client.post(
        f"{settings.API_V1_STR}/documents/",
        headers=superuser_token_headers,
        json={
            "document_type": "id_document",
            "file_name": "ine.pdf",
            "file_url": "https://storage.example.com/ine.pdf",
            "application_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Read by ID
# ---------------------------------------------------------------------------


def test_read_document_by_id(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Read a document by its ID."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)
    document = _create_document_in_db(db, application.id)

    r = client.get(
        f"{settings.API_V1_STR}/documents/{document.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(document.id)


def test_read_document_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/documents/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Update
# ---------------------------------------------------------------------------


def test_update_document(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Update a document's metadata."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)
    document = _create_document_in_db(db, application.id)

    r = client.patch(
        f"{settings.API_V1_STR}/documents/{document.id}",
        headers=superuser_token_headers,
        json={"file_name": "updated.pdf"},
    )
    assert r.status_code == 200
    assert r.json()["file_name"] == "updated.pdf"


def test_update_document_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.patch(
        f"{settings.API_V1_STR}/documents/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"file_name": "nope.pdf"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Delete
# ---------------------------------------------------------------------------


def test_delete_document(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can delete a document."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)
    document = _create_document_in_db(db, application.id)

    r = client.delete(
        f"{settings.API_V1_STR}/documents/{document.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Document deleted successfully"


def test_delete_document_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/documents/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


def test_delete_document_other_facilitator_forbidden(
    client: TestClient, db: Session
) -> None:
    """Facilitator cannot delete a document from another facilitator's application."""
    headers_a, _, _ = _setup_facilitator_with_app(client, db)
    _, facilitator_b = create_random_facilitator(db)
    beneficiary_b = create_random_beneficiary(db, facilitator=facilitator_b)
    application_b = create_random_application(db, beneficiary=beneficiary_b)
    document_b = _create_document_in_db(db, application_b.id)

    r = client.delete(
        f"{settings.API_V1_STR}/documents/{document_b.id}",
        headers=headers_a,
    )
    assert r.status_code == 403
