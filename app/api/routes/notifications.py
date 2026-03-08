import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_admin_or_superuser
from app.models import (
    Message,
    Notification,
    NotificationCreate,
    NotificationPublic,
    NotificationsPublic,
    NotificationUpdate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# User-facing endpoints (own notifications)
# ---------------------------------------------------------------------------


@router.get("/me", response_model=NotificationsPublic)
def read_my_notifications(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Retrieve the current user's notifications."""
    count_statement = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(col(Notification.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    notifications = session.exec(statement).all()
    return NotificationsPublic(data=notifications, count=count)


@router.patch("/me/{notification_id}", response_model=NotificationPublic)
def update_my_notification(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    notification_id: uuid.UUID,
    notification_in: NotificationUpdate,
) -> Any:
    """Update a notification (e.g. mark as read).

    Users can only update their own notifications.
    """
    notification = session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    notification = crud.update_notification(
        session=session,
        db_notification=notification,
        notification_in=notification_in,
    )
    return notification


@router.delete("/me/{notification_id}")
def delete_my_notification(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    notification_id: uuid.UUID,
) -> Message:
    """Delete one of the current user's notifications."""
    notification = session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    session.delete(notification)
    session.commit()
    return Message(message="Notification deleted successfully")


# ---------------------------------------------------------------------------
# Admin endpoints (manage any user's notifications)
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=NotificationsPublic,
    dependencies=[Depends(get_current_admin_or_superuser)],
)
def read_notifications(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    user_id: uuid.UUID | None = None,
) -> Any:
    """Retrieve notifications (admin/superuser).

    Optionally filter by ``user_id``.
    """
    base = select(Notification)
    count_base = select(func.count()).select_from(Notification)
    if user_id:
        base = base.where(Notification.user_id == user_id)
        count_base = count_base.where(Notification.user_id == user_id)
    count = session.exec(count_base).one()
    statement = (
        base.order_by(col(Notification.created_at).desc()).offset(skip).limit(limit)
    )
    notifications = session.exec(statement).all()
    return NotificationsPublic(data=notifications, count=count)


@router.post(
    "/",
    response_model=NotificationPublic,
    dependencies=[Depends(get_current_admin_or_superuser)],
)
def create_notification(
    *,
    session: SessionDep,
    notification_in: NotificationCreate,
) -> Any:
    """Create a notification for a user.

    Only admins and superusers can send notifications.
    """
    from app.models import User

    target_user = session.get(User, notification_in.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    notification = crud.create_notification(
        session=session, notification_in=notification_in
    )
    return notification


@router.delete(
    "/{notification_id}",
    dependencies=[Depends(get_current_admin_or_superuser)],
)
def delete_notification(
    *,
    session: SessionDep,
    notification_id: uuid.UUID,
) -> Message:
    """Delete any notification (admin/superuser)."""
    notification = session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    session.delete(notification)
    session.commit()
    return Message(message="Notification deleted successfully")
