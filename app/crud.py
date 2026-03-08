import uuid
from typing import Any

from sqlmodel import Session, select

from app.core.integrity import compute_integrity_hash
from app.core.security import get_password_hash, verify_password
from app.models import (
    AdminUser,
    AdminUserCreate,
    AdminUserUpdate,
    Application,
    ApplicationCreate,
    ApplicationStatus,
    ApplicationStatusHistory,
    ApplicationStatusHistoryCreate,
    ApplicationUpdate,
    AuditLog,
    AuditLogCreate,
    Beneficiary,
    BeneficiaryCreate,
    BeneficiaryUpdate,
    Document,
    DocumentCreate,
    DocumentUpdate,
    Facilitator,
    FacilitatorCreate,
    FacilitatorUpdate,
    Notification,
    NotificationCreate,
    NotificationUpdate,
    User,
    UserCreate,
    UserUpdate,
)

# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def get_user_by_username(*, session: Session, username: str) -> User | None:
    statement = select(User).where(User.username == username)
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


# ---------------------------------------------------------------------------
# Facilitator CRUD
# ---------------------------------------------------------------------------


def create_facilitator(
    *, session: Session, facilitator_in: FacilitatorCreate
) -> Facilitator:
    db_obj = Facilitator.model_validate(facilitator_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_facilitator(
    *,
    session: Session,
    db_facilitator: Facilitator,
    facilitator_in: FacilitatorUpdate,
) -> Facilitator:
    facilitator_data = facilitator_in.model_dump(exclude_unset=True)
    db_facilitator.sqlmodel_update(facilitator_data)
    session.add(db_facilitator)
    session.commit()
    session.refresh(db_facilitator)
    return db_facilitator


def get_facilitator_by_user_id(
    *, session: Session, user_id: uuid.UUID
) -> Facilitator | None:
    statement = select(Facilitator).where(Facilitator.user_id == user_id)
    return session.exec(statement).first()


# ---------------------------------------------------------------------------
# Beneficiary CRUD
# ---------------------------------------------------------------------------


def create_beneficiary(
    *, session: Session, beneficiary_in: BeneficiaryCreate
) -> Beneficiary:
    db_obj = Beneficiary.model_validate(beneficiary_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_beneficiary(
    *,
    session: Session,
    db_beneficiary: Beneficiary,
    beneficiary_in: BeneficiaryUpdate,
) -> Beneficiary:
    beneficiary_data = beneficiary_in.model_dump(exclude_unset=True)
    db_beneficiary.sqlmodel_update(beneficiary_data)
    session.add(db_beneficiary)
    session.commit()
    session.refresh(db_beneficiary)
    return db_beneficiary


def get_beneficiary_by_curp(*, session: Session, curp: str) -> Beneficiary | None:
    """Look up a beneficiary by CURP.

    Because CURP is stored encrypted, we cannot use a simple WHERE clause.
    Instead we scan all beneficiaries and compare the decrypted value.
    For large datasets a hashed-CURP index column should be added.
    """
    statement = select(Beneficiary)
    beneficiaries = session.exec(statement).all()
    for b in beneficiaries:
        if b.curp == curp:
            return b
    return None


# ---------------------------------------------------------------------------
# Application CRUD
# ---------------------------------------------------------------------------


def create_application(
    *, session: Session, application_in: ApplicationCreate
) -> Application:
    db_obj = Application.model_validate(application_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_application(
    *,
    session: Session,
    db_application: Application,
    application_in: ApplicationUpdate,
) -> Application:
    application_data = application_in.model_dump(exclude_unset=True)
    db_application.sqlmodel_update(application_data)
    session.add(db_application)
    session.commit()
    session.refresh(db_application)
    return db_application


# ---------------------------------------------------------------------------
# Application Status History CRUD
# ---------------------------------------------------------------------------


# Valid status transitions
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.draft: {
        ApplicationStatus.submitted,
        ApplicationStatus.cancelled,
    },
    ApplicationStatus.submitted: {
        ApplicationStatus.under_review,
        ApplicationStatus.cancelled,
    },
    ApplicationStatus.under_review: {
        ApplicationStatus.approved,
        ApplicationStatus.rejected,
        ApplicationStatus.cancelled,
    },
    ApplicationStatus.approved: set(),
    ApplicationStatus.rejected: {
        ApplicationStatus.under_review,
    },
    ApplicationStatus.cancelled: set(),
}


def is_valid_transition(*, current: ApplicationStatus, new: ApplicationStatus) -> bool:
    """Check whether a status transition is allowed."""
    return new in VALID_TRANSITIONS.get(current, set())


def create_status_history(
    *,
    session: Session,
    application: Application,
    history_in: ApplicationStatusHistoryCreate,
    changed_by: uuid.UUID | None = None,
) -> ApplicationStatusHistory:
    """Record a status change and update the application's status."""
    db_obj = ApplicationStatusHistory(
        application_id=application.id,
        previous_status=application.status,
        new_status=history_in.new_status,
        comment=history_in.comment,
        changed_by=changed_by,
    )
    application.status = history_in.new_status

    # Set timestamps on the application based on the new status
    from app.models import get_datetime_utc

    now = get_datetime_utc()
    if history_in.new_status == ApplicationStatus.submitted:
        application.submitted_at = now
    elif history_in.new_status in (
        ApplicationStatus.approved,
        ApplicationStatus.rejected,
    ):
        application.reviewed_at = now
        application.reviewed_by = changed_by
        if (
            history_in.new_status == ApplicationStatus.rejected
            and history_in.rejection_reason
        ):
            application.rejection_reason = history_in.rejection_reason

    application.updated_at = now

    session.add(db_obj)
    session.add(application)
    session.commit()
    session.refresh(db_obj)
    session.refresh(application)
    return db_obj


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------


def create_document(
    *,
    session: Session,
    document_in: DocumentCreate,
    uploaded_by: uuid.UUID | None = None,
) -> Document:
    db_obj = Document.model_validate(document_in, update={"uploaded_by": uploaded_by})
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_document(
    *,
    session: Session,
    db_document: Document,
    document_in: DocumentUpdate,
) -> Document:
    document_data = document_in.model_dump(exclude_unset=True)
    db_document.sqlmodel_update(document_data)
    session.add(db_document)
    session.commit()
    session.refresh(db_document)
    return db_document


# ---------------------------------------------------------------------------
# AdminUser CRUD
# ---------------------------------------------------------------------------


def create_admin_user(*, session: Session, admin_user_in: AdminUserCreate) -> AdminUser:
    db_obj = AdminUser.model_validate(admin_user_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_admin_user(
    *,
    session: Session,
    db_admin_user: AdminUser,
    admin_user_in: AdminUserUpdate,
) -> AdminUser:
    admin_user_data = admin_user_in.model_dump(exclude_unset=True)
    db_admin_user.sqlmodel_update(admin_user_data)
    session.add(db_admin_user)
    session.commit()
    session.refresh(db_admin_user)
    return db_admin_user


def get_admin_user_by_user_id(
    *, session: Session, user_id: uuid.UUID
) -> AdminUser | None:
    statement = select(AdminUser).where(AdminUser.user_id == user_id)
    return session.exec(statement).first()


# ---------------------------------------------------------------------------
# AuditLog CRUD
# ---------------------------------------------------------------------------


def create_audit_log(
    *,
    session: Session,
    audit_log_in: AuditLogCreate,
    user_id: uuid.UUID,
    secret_key: str,
) -> AuditLog:
    """Create an audit log entry with HMAC-SHA256 integrity hash.

    The integrity hash is computed AFTER the initial DB round-trip so that the
    ``created_at`` timestamp used in the hash matches exactly what PostgreSQL
    stores and returns (avoiding microsecond / timezone representation drift).
    """
    db_obj = AuditLog.model_validate(
        audit_log_in,
        update={
            "user_id": user_id,
            "integrity_hash": "",  # placeholder – computed after insert
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)

    # Now compute the hash using the DB-round-tripped created_at
    assert db_obj.created_at is not None  # guaranteed after refresh
    db_obj.integrity_hash = compute_integrity_hash(
        secret_key=secret_key,
        action=db_obj.action,
        resource_type=db_obj.resource_type,
        resource_id=db_obj.resource_id,
        user_id=db_obj.user_id,
        created_at=db_obj.created_at,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


# ---------------------------------------------------------------------------
# Notification CRUD
# ---------------------------------------------------------------------------


def create_notification(
    *, session: Session, notification_in: NotificationCreate
) -> Notification:
    db_obj = Notification.model_validate(notification_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_notification(
    *,
    session: Session,
    db_notification: Notification,
    notification_in: NotificationUpdate,
) -> Notification:
    notification_data = notification_in.model_dump(exclude_unset=True)
    db_notification.sqlmodel_update(notification_data)
    session.add(db_notification)
    session.commit()
    session.refresh(db_notification)
    return db_notification
