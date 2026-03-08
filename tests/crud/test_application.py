from sqlmodel import Session

from app import crud
from app.models import (
    ApplicationCreate,
    ApplicationStatus,
    ApplicationStatusHistoryCreate,
    ApplicationUpdate,
)
from tests.utils.application import create_random_application
from tests.utils.beneficiary import create_random_beneficiary
from tests.utils.facilitator import create_random_facilitator


def test_create_application(db: Session) -> None:
    """Create an application linked to a beneficiary."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application_in = ApplicationCreate(
        program_name="Programa Bienestar",
        description="Social aid program",
        beneficiary_id=beneficiary.id,
    )
    application = crud.create_application(session=db, application_in=application_in)
    assert application.program_name == "Programa Bienestar"
    assert application.beneficiary_id == beneficiary.id
    assert application.status == ApplicationStatus.draft


def test_update_application(db: Session) -> None:
    """Update an application's basic fields."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)

    update_in = ApplicationUpdate(program_name="Updated Program")
    updated = crud.update_application(
        session=db, db_application=application, application_in=update_in
    )
    assert updated.program_name == "Updated Program"
    assert updated.id == application.id


def test_valid_transition_submit() -> None:
    """Transition from draft to submitted is valid."""
    assert crud.is_valid_transition(
        current=ApplicationStatus.draft, new=ApplicationStatus.submitted
    )


def test_invalid_transition_draft_to_approved() -> None:
    """Transition from draft to approved is invalid (must go through review)."""
    assert not crud.is_valid_transition(
        current=ApplicationStatus.draft, new=ApplicationStatus.approved
    )


def test_create_status_history(db: Session) -> None:
    """Create a status history entry and update application status."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)

    assert application.status == ApplicationStatus.draft

    history_in = ApplicationStatusHistoryCreate(
        new_status=ApplicationStatus.submitted,
        comment="Initial submission",
    )
    user, _ = create_random_facilitator(db)
    history = crud.create_status_history(
        session=db,
        application=application,
        history_in=history_in,
        changed_by=user.id,
    )
    assert history.previous_status == ApplicationStatus.draft
    assert history.new_status == ApplicationStatus.submitted
    assert history.comment == "Initial submission"
    assert history.changed_by == user.id

    # Application status should be updated
    db.refresh(application)
    assert application.status == ApplicationStatus.submitted
    assert application.submitted_at is not None


def test_create_status_history_rejection(db: Session) -> None:
    """Rejection sets reviewed_at, reviewed_by, and rejection_reason."""
    _, facilitator = create_random_facilitator(db)
    beneficiary = create_random_beneficiary(db, facilitator=facilitator)
    application = create_random_application(db, beneficiary=beneficiary)
    reviewer_user, _ = create_random_facilitator(db)

    # draft → submitted → under_review → rejected
    crud.create_status_history(
        session=db,
        application=application,
        history_in=ApplicationStatusHistoryCreate(
            new_status=ApplicationStatus.submitted
        ),
        changed_by=reviewer_user.id,
    )
    crud.create_status_history(
        session=db,
        application=application,
        history_in=ApplicationStatusHistoryCreate(
            new_status=ApplicationStatus.under_review
        ),
        changed_by=reviewer_user.id,
    )
    crud.create_status_history(
        session=db,
        application=application,
        history_in=ApplicationStatusHistoryCreate(
            new_status=ApplicationStatus.rejected,
            rejection_reason="Incomplete documentation",
        ),
        changed_by=reviewer_user.id,
    )

    db.refresh(application)
    assert application.status == ApplicationStatus.rejected
    assert application.reviewed_at is not None
    assert application.reviewed_by == reviewer_user.id
    assert application.rejection_reason == "Incomplete documentation"
