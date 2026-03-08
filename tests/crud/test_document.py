from sqlmodel import Session

from app import crud
from app.models import DocumentCreate, DocumentType, DocumentUpdate
from tests.utils.application import create_random_application
from tests.utils.beneficiary import create_random_beneficiary
from tests.utils.facilitator import create_random_facilitator


def test_create_document(db: Session) -> None:
    """Create a document linked to an application."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)
    user, _ = create_random_facilitator(db)

    doc_in = DocumentCreate(
        document_type=DocumentType.id_document,
        file_name="ine_front.pdf",
        file_url="https://storage.example.com/docs/ine_front.pdf",
        description="INE front side",
        application_id=application.id,
    )
    document = crud.create_document(session=db, document_in=doc_in, uploaded_by=user.id)
    assert document.document_type == DocumentType.id_document
    assert document.file_name == "ine_front.pdf"
    assert document.application_id == application.id
    assert document.uploaded_by == user.id


def test_update_document(db: Session) -> None:
    """Update a document's metadata."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)

    doc_in = DocumentCreate(
        document_type=DocumentType.proof_of_address,
        file_name="comprobante.pdf",
        file_url="https://storage.example.com/docs/comprobante.pdf",
        application_id=application.id,
    )
    document = crud.create_document(session=db, document_in=doc_in)

    update_in = DocumentUpdate(file_name="comprobante_v2.pdf")
    updated = crud.update_document(
        session=db, db_document=document, document_in=update_in
    )
    assert updated.file_name == "comprobante_v2.pdf"
    assert updated.id == document.id


def test_create_document_without_uploader(db: Session) -> None:
    """Create a document without specifying uploaded_by."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)

    doc_in = DocumentCreate(
        document_type=DocumentType.birth_certificate,
        file_name="acta_nacimiento.pdf",
        file_url="https://storage.example.com/docs/acta.pdf",
        application_id=application.id,
    )
    document = crud.create_document(session=db, document_in=doc_in)
    assert document.uploaded_by is None
    assert document.uploaded_at is not None
