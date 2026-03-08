import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_admin_or_superuser
from app.core.config import settings
from app.core.integrity import verify_integrity_hash
from app.models import (
    AuditLog,
    AuditLogCreate,
    AuditLogPublic,
    AuditLogsPublic,
)

router = APIRouter(
    prefix="/audit-logs",
    tags=["audit-logs"],
    dependencies=[Depends(get_current_admin_or_superuser)],
)


@router.get("/", response_model=AuditLogsPublic)
def read_audit_logs(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Retrieve audit log entries.

    Only accessible to admins and superusers.
    """
    count_statement = select(func.count()).select_from(AuditLog)
    count = session.exec(count_statement).one()
    statement = (
        select(AuditLog)
        .order_by(col(AuditLog.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    audit_logs = session.exec(statement).all()
    return AuditLogsPublic(data=audit_logs, count=count)


@router.get("/{audit_log_id}", response_model=AuditLogPublic)
def read_audit_log_by_id(
    audit_log_id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """Get a specific audit log entry by id."""
    audit_log = session.get(AuditLog, audit_log_id)
    if not audit_log:
        raise HTTPException(status_code=404, detail="Audit log entry not found")
    return audit_log


@router.post("/", response_model=AuditLogPublic)
def create_audit_log(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    audit_log_in: AuditLogCreate,
) -> Any:
    """Create a new audit log entry.

    The integrity hash is computed automatically using HMAC-SHA256.
    """
    audit_log = crud.create_audit_log(
        session=session,
        audit_log_in=audit_log_in,
        user_id=current_user.id,
        secret_key=settings.SECRET_KEY,
    )
    return audit_log


@router.get("/{audit_log_id}/verify")
def verify_audit_log_integrity(
    audit_log_id: uuid.UUID,
    session: SessionDep,
) -> dict[str, Any]:
    """Verify the integrity of an audit log entry.

    Recomputes the HMAC-SHA256 hash and compares it with the stored one.
    Returns the verification result.
    """
    audit_log = session.get(AuditLog, audit_log_id)
    if not audit_log:
        raise HTTPException(status_code=404, detail="Audit log entry not found")

    if not audit_log.created_at:
        raise HTTPException(
            status_code=400,
            detail="Audit log entry has no created_at timestamp",
        )

    is_valid = verify_integrity_hash(
        secret_key=settings.SECRET_KEY,
        action=audit_log.action,
        resource_type=audit_log.resource_type,
        resource_id=audit_log.resource_id,
        user_id=audit_log.user_id,
        created_at=audit_log.created_at,
        integrity_hash=audit_log.integrity_hash,
    )
    return {"audit_log_id": str(audit_log_id), "integrity_valid": is_valid}
