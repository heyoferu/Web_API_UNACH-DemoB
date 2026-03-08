import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import NotificationCreate, NotificationType, UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string, random_username

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_user_with_notification(
    client: TestClient, db: Session
) -> tuple[dict[str, str], str, str]:
    """Create a user and a notification for them.

    Returns (auth_headers, user_id_str, notification_id_str).
    """
    password = random_lower_string()
    user_in = UserCreate(
        email=random_email(),
        password=password,
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    notification_in = NotificationCreate(
        user_id=user.id,
        title="Hello",
        message="Test notification",
        notification_type=NotificationType.info,
    )
    notification = crud.create_notification(session=db, notification_in=notification_in)
    headers = user_authentication_headers(
        client=client, email=user.email, password=password
    )
    return headers, str(user.id), str(notification.id)


# ---------------------------------------------------------------------------
# My notifications — list
# ---------------------------------------------------------------------------


def test_read_my_notifications(client: TestClient, db: Session) -> None:
    headers, _, _ = _create_user_with_notification(client, db)
    r = client.get(
        f"{settings.API_V1_STR}/notifications/me",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1


def test_read_my_notifications_empty(client: TestClient, db: Session) -> None:
    """User with no notifications gets empty list."""
    password = random_lower_string()
    user_in = UserCreate(
        email=random_email(),
        password=password,
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    headers = user_authentication_headers(
        client=client, email=user.email, password=password
    )
    r = client.get(
        f"{settings.API_V1_STR}/notifications/me",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["count"] == 0


# ---------------------------------------------------------------------------
# My notifications — mark as read
# ---------------------------------------------------------------------------


def test_update_my_notification_mark_as_read(client: TestClient, db: Session) -> None:
    headers, _, notification_id = _create_user_with_notification(client, db)
    r = client.patch(
        f"{settings.API_V1_STR}/notifications/me/{notification_id}",
        headers=headers,
        json={"is_read": True},
    )
    assert r.status_code == 200
    assert r.json()["is_read"] is True


def test_update_my_notification_not_found(client: TestClient, db: Session) -> None:
    headers, _, _ = _create_user_with_notification(client, db)
    r = client.patch(
        f"{settings.API_V1_STR}/notifications/me/{uuid.uuid4()}",
        headers=headers,
        json={"is_read": True},
    )
    assert r.status_code == 404


def test_update_my_notification_other_users_forbidden(
    client: TestClient, db: Session
) -> None:
    """User cannot mark another user's notification as read."""
    _, _, notification_id = _create_user_with_notification(client, db)
    # Create a different user
    password2 = random_lower_string()
    user2_in = UserCreate(
        email=random_email(),
        password=password2,
        username=random_username(),
    )
    user2 = crud.create_user(session=db, user_create=user2_in)
    headers2 = user_authentication_headers(
        client=client, email=user2.email, password=password2
    )
    r = client.patch(
        f"{settings.API_V1_STR}/notifications/me/{notification_id}",
        headers=headers2,
        json={"is_read": True},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# My notifications — delete
# ---------------------------------------------------------------------------


def test_delete_my_notification(client: TestClient, db: Session) -> None:
    headers, _, notification_id = _create_user_with_notification(client, db)
    r = client.delete(
        f"{settings.API_V1_STR}/notifications/me/{notification_id}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Notification deleted successfully"


def test_delete_my_notification_not_found(client: TestClient, db: Session) -> None:
    headers, _, _ = _create_user_with_notification(client, db)
    r = client.delete(
        f"{settings.API_V1_STR}/notifications/me/{uuid.uuid4()}",
        headers=headers,
    )
    assert r.status_code == 404


def test_delete_my_notification_other_users_forbidden(
    client: TestClient, db: Session
) -> None:
    _, _, notification_id = _create_user_with_notification(client, db)
    password2 = random_lower_string()
    user2_in = UserCreate(
        email=random_email(),
        password=password2,
        username=random_username(),
    )
    user2 = crud.create_user(session=db, user_create=user2_in)
    headers2 = user_authentication_headers(
        client=client, email=user2.email, password=password2
    )
    r = client.delete(
        f"{settings.API_V1_STR}/notifications/me/{notification_id}",
        headers=headers2,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Admin — list all notifications
# ---------------------------------------------------------------------------


def test_read_all_notifications_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    # Create a notification for a user
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    crud.create_notification(
        session=db,
        notification_in=NotificationCreate(
            user_id=user.id,
            title="Admin list test",
            message="Should show up in admin list",
            notification_type=NotificationType.success,
        ),
    )
    r = client.get(
        f"{settings.API_V1_STR}/notifications/",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_read_all_notifications_filter_by_user(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    crud.create_notification(
        session=db,
        notification_in=NotificationCreate(
            user_id=user.id,
            title="Filter test",
            message="Filtered",
            notification_type=NotificationType.warning,
        ),
    )
    r = client.get(
        f"{settings.API_V1_STR}/notifications/?user_id={user.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    for item in data["data"]:
        assert item["user_id"] == str(user.id)


def test_read_all_notifications_as_facilitator_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/notifications/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Admin — create notification
# ---------------------------------------------------------------------------


def test_create_notification_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    r = client.post(
        f"{settings.API_V1_STR}/notifications/",
        headers=superuser_token_headers,
        json={
            "user_id": str(user.id),
            "title": "Welcome",
            "message": "Welcome to the platform!",
            "notification_type": "success",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Welcome"
    assert data["user_id"] == str(user.id)
    assert data["is_read"] is False


def test_create_notification_target_user_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/notifications/",
        headers=superuser_token_headers,
        json={
            "user_id": str(uuid.uuid4()),
            "title": "Test",
            "message": "Should fail",
            "notification_type": "info",
        },
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Admin — delete any notification
# ---------------------------------------------------------------------------


def test_admin_delete_notification(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        username=random_username(),
    )
    user = crud.create_user(session=db, user_create=user_in)
    notification = crud.create_notification(
        session=db,
        notification_in=NotificationCreate(
            user_id=user.id,
            title="Delete me",
            message="Admin delete test",
            notification_type=NotificationType.error,
        ),
    )
    r = client.delete(
        f"{settings.API_V1_STR}/notifications/{notification.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200


def test_admin_delete_notification_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/notifications/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
