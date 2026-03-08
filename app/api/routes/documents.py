import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Application,
    Beneficiary,
    Document,
    DocumentCreate,
    DocumentPublic,
    DocumentsPublic,
    DocumentUpdate,
    Message,
    UserRole,
)

router = APIRouter(prefix="/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_document_access(
    *,
    session: SessionDep,
    application: Application,
    current_user: CurrentUser,
) -> None:
    """Raise 403 if the current user cannot access documents for this application."""
    if current_user.role in (UserRole.admin, UserRole.superuser):
        return
    if current_user.role == UserRole.facilitator:
        facilitator = crud.get_facilitator_by_user_id(
            session=session, user_id=current_user.id
        )
        if facilitator:
            beneficiary = session.get(Beneficiary, application.beneficiary_id)
            if beneficiary and beneficiary.facilitator_id == facilitator.id:
                return
    raise HTTPException(
        status_code=403, detail="The user doesn't have enough privileges"
    )


# ---------------------------------------------------------------------------
# Document CRUD endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=DocumentsPublic)
def read_documents(
    session: SessionDep,
    current_user: CurrentUser,
    application_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Retrieve documents for a specific application."""
    application = session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _check_document_access(
        session=session, application=application, current_user=current_user
    )

    count_statement = (
        select(func.count())
        .select_from(Document)
        .where(Document.application_id == application_id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Document)
        .where(Document.application_id == application_id)
        .order_by(col(Document.uploaded_at).desc())
        .offset(skip)
        .limit(limit)
    )
    documents = session.exec(statement).all()
    return DocumentsPublic(data=documents, count=count)


@router.post("/", response_model=DocumentPublic)
def create_document(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    document_in: DocumentCreate,
) -> Any:
    """Upload a document reference for an application."""
    application = session.get(Application, document_in.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _check_document_access(
        session=session, application=application, current_user=current_user
    )

    document = crud.create_document(
        session=session,
        document_in=document_in,
        uploaded_by=current_user.id,
    )
    return document


@router.get("/{document_id}", response_model=DocumentPublic)
def read_document_by_id(
    document_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """Get a specific document by id."""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    application = session.get(Application, document.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _check_document_access(
        session=session, application=application, current_user=current_user
    )
    return document


@router.patch("/{document_id}", response_model=DocumentPublic)
def update_document(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    document_id: uuid.UUID,
    document_in: DocumentUpdate,
) -> Any:
    """Update a document's metadata."""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    application = session.get(Application, document.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _check_document_access(
        session=session, application=application, current_user=current_user
    )

    document = crud.update_document(
        session=session, db_document=document, document_in=document_in
    )
    return document


@router.delete("/{document_id}")
def delete_document(
    document_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Delete a document."""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    application = session.get(Application, document.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _check_document_access(
        session=session, application=application, current_user=current_user
    )

    session.delete(document)
    session.commit()
    return Message(message="Document deleted successfully")
