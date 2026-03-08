import uuid

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.integrity import verify_integrity_hash
from app.models import (
    AdminRole,
    AdminUserCreate,
    AdminUserUpdate,
    AuditLogCreate,
    NotificationCreate,
    NotificationType,
    NotificationUpdate,
    UserCreate,
    UserRole,
)
from tests.utils.utils import random_email, random_lower_string, random_username

# ---------------------------------------------------------------------------
# AdminUser CRUD tests
# ---------------------------------------------------------------------------


def test_create_admin_user(db: Session) -> None:
    email = random_email()
    user_in = UserCreate(
        email=email,
        password=random_lower_string(),
        username=random_username(),
        role=UserRole.admin,
    )
    user = crud.create_user(session=db, user_create=user_in)
    admin_user_in = AdminUserCreate(
        user_id=user.id,
        admin_role=AdminRole.document_validator,
        department="Validaciones",
    )
    admin_user = crud.create_admin_user(session=db, admin_user_in=admin_user_in)
    assert admin_user.user_id == user.id
    assert admin_user.admin_role == AdminRole.document_validator
    assert admin_user.department == "Validaciones"


def test_update_admin_user(db: Session) -> None:
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
        role=UserRole.admin,
    )
    user = crud.create_user(session=db, user_create=user_in)
    admin_user_in = AdminUserCreate(
        user_id=user.id,
        admin_role=AdminRole.document_validator,
    )
    admin_user = crud.create_admin_user(session=db, admin_user_in=admin_user_in)
    update_in = AdminUserUpdate(admin_role=AdminRole.application_approver)
    updated = crud.update_admin_user(
        session=db, db_admin_user=admin_user, admin_user_in=update_in
    )
    assert updated.admin_role == AdminRole.application_approver


def test_get_admin_user_by_user_id(db: Session) -> None:
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
        role=UserRole.admin,
    )
    user = crud.create_user(session=db, user_create=user_in)
    admin_user_in = AdminUserCreate(
        user_id=user.id,
        admin_role=AdminRole.system_administrator,
    )
    crud.create_admin_user(session=db, admin_user_in=admin_user_in)
    found = crud.get_admin_user_by_user_id(session=db, user_id=user.id)
    assert found is not None
    assert found.user_id == user.id


def test_get_admin_user_by_user_id_not_found(db: Session) -> None:
    found = crud.get_admin_user_by_user_id(session=db, user_id=uuid.uuid4())
    assert found is None


# ---------------------------------------------------------------------------
# AuditLog CRUD tests
# ---------------------------------------------------------------------------


def test_create_audit_log(db: Session) -> None:
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    resource_id = uuid.uuid4()
    audit_log_in = AuditLogCreate(
        action="user.create",
        resource_type="user",
        resource_id=resource_id,
        details="Created a test user",
    )
    audit_log = crud.create_audit_log(
        session=db,
        audit_log_in=audit_log_in,
        user_id=user.id,
        secret_key=settings.SECRET_KEY,
    )
    assert audit_log.action == "user.create"
    assert audit_log.resource_type == "user"
    assert audit_log.resource_id == resource_id
    assert audit_log.user_id == user.id
    assert audit_log.integrity_hash is not None
    assert len(audit_log.integrity_hash) == 64


def test_audit_log_integrity_verification(db: Session) -> None:
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    audit_log_in = AuditLogCreate(
        action="beneficiary.update",
        resource_type="beneficiary",
        resource_id=uuid.uuid4(),
    )
    audit_log = crud.create_audit_log(
        session=db,
        audit_log_in=audit_log_in,
        user_id=user.id,
        secret_key=settings.SECRET_KEY,
    )
    assert audit_log.created_at is not None
    is_valid = verify_integrity_hash(
        secret_key=settings.SECRET_KEY,
        action=audit_log.action,
        resource_type=audit_log.resource_type,
        resource_id=audit_log.resource_id,
        user_id=audit_log.user_id,
        created_at=audit_log.created_at,
        integrity_hash=audit_log.integrity_hash,
    )
    assert is_valid is True


# ---------------------------------------------------------------------------
# Notification CRUD tests
# ---------------------------------------------------------------------------


def test_create_notification(db: Session) -> None:
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    notification_in = NotificationCreate(
        user_id=user.id,
        title="Test Notification",
        message="This is a test notification",
        notification_type=NotificationType.info,
    )
    notification = crud.create_notification(session=db, notification_in=notification_in)
    assert notification.user_id == user.id
    assert notification.title == "Test Notification"
    assert notification.notification_type == NotificationType.info
    assert notification.is_read is False


def test_update_notification_mark_as_read(db: Session) -> None:
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    notification_in = NotificationCreate(
        user_id=user.id,
        title="Unread",
        message="Mark me as read",
        notification_type=NotificationType.warning,
    )
    notification = crud.create_notification(session=db, notification_in=notification_in)
    assert notification.is_read is False
    update_in = NotificationUpdate(is_read=True)
    updated = crud.update_notification(
        session=db, db_notification=notification, notification_in=update_in
    )
    assert updated.is_read is True
