import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_admin_or_superuser,
)
from app.models import (
    Application,
    ApplicationCreate,
    ApplicationPublic,
    ApplicationsPublic,
    ApplicationStatus,
    ApplicationStatusHistoriesPublic,
    ApplicationStatusHistory,
    ApplicationStatusHistoryCreate,
    ApplicationStatusHistoryPublic,
    ApplicationUpdate,
    Beneficiary,
    Message,
    UserRole,
)

router = APIRouter(prefix="/applications", tags=["applications"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_facilitator_id_for_user(
    session: SessionDep, current_user_id: uuid.UUID
) -> uuid.UUID:
    """Return the facilitator id for the given user, or raise 404."""
    facilitator = crud.get_facilitator_by_user_id(
        session=session, user_id=current_user_id
    )
    if not facilitator:
        raise HTTPException(status_code=404, detail="Facilitator profile not found")
    return facilitator.id


def _check_application_access(
    *,
    session: SessionDep,
    application: Application,
    current_user: CurrentUser,
) -> None:
    """Raise 403 if the current user cannot access this application."""
    if current_user.role in (UserRole.admin, UserRole.superuser):
        return
    if current_user.role == UserRole.facilitator:
        facilitator_id = _get_facilitator_id_for_user(session, current_user.id)
        beneficiary = session.get(Beneficiary, application.beneficiary_id)
        if beneficiary and beneficiary.facilitator_id == facilitator_id:
            return
    raise HTTPException(
        status_code=403, detail="The user doesn't have enough privileges"
    )


# ---------------------------------------------------------------------------
# Application CRUD endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=ApplicationsPublic)
def read_applications(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Retrieve applications.

    Facilitators see only applications for their beneficiaries.
    Admins and superusers see all.
    """
    if current_user.role == UserRole.facilitator:
        facilitator_id = _get_facilitator_id_for_user(session, current_user.id)
        count_statement = (
            select(func.count())
            .select_from(Application)
            .join(Beneficiary, Application.beneficiary_id == Beneficiary.id)  # type: ignore[arg-type]
            .where(Beneficiary.facilitator_id == facilitator_id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Application)
            .join(Beneficiary, Application.beneficiary_id == Beneficiary.id)  # type: ignore[arg-type]
            .where(Beneficiary.facilitator_id == facilitator_id)
            .order_by(col(Application.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
    elif current_user.role in (UserRole.admin, UserRole.superuser):
        count_statement = select(func.count()).select_from(Application)
        count = session.exec(count_statement).one()
        statement = (
            select(Application)
            .order_by(col(Application.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
    else:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )

    applications = session.exec(statement).all()
    return ApplicationsPublic(data=applications, count=count)


@router.post("/", response_model=ApplicationPublic)
def create_application(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    application_in: ApplicationCreate,
) -> Any:
    """Create a new application.

    Facilitators can only create applications for their own beneficiaries.
    Admins and superusers can create for any beneficiary.
    """
    beneficiary = session.get(Beneficiary, application_in.beneficiary_id)
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    if current_user.role == UserRole.facilitator:
        facilitator_id = _get_facilitator_id_for_user(session, current_user.id)
        if beneficiary.facilitator_id != facilitator_id:
            raise HTTPException(
                status_code=403,
                detail="Facilitators can only create applications for their own beneficiaries",
            )
    elif current_user.role not in (UserRole.admin, UserRole.superuser):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )

    application = crud.create_application(
        session=session, application_in=application_in
    )
    return application


@router.get("/{application_id}", response_model=ApplicationPublic)
def read_application_by_id(
    application_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """Get a specific application by id."""
    application = session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_application_access(
        session=session, application=application, current_user=current_user
    )
    return application


@router.patch("/{application_id}", response_model=ApplicationPublic)
def update_application(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    application_id: uuid.UUID,
    application_in: ApplicationUpdate,
) -> Any:
    """Update an application's basic fields (program_name, description).

    Only draft applications can be updated.
    """
    application = session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_application_access(
        session=session, application=application, current_user=current_user
    )
    if application.status != ApplicationStatus.draft:
        raise HTTPException(
            status_code=400,
            detail="Only draft applications can be updated",
        )
    application = crud.update_application(
        session=session, db_application=application, application_in=application_in
    )
    return application


@router.delete(
    "/{application_id}",
    dependencies=[Depends(get_current_admin_or_superuser)],
)
def delete_application(session: SessionDep, application_id: uuid.UUID) -> Message:
    """Delete an application."""
    application = session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    session.delete(application)
    session.commit()
    return Message(message="Application deleted successfully")


# ---------------------------------------------------------------------------
# Status Transition endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/{application_id}/status",
    response_model=ApplicationStatusHistoryPublic,
)
def transition_application_status(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    application_id: uuid.UUID,
    status_in: ApplicationStatusHistoryCreate,
) -> Any:
    """Transition an application to a new status.

    Validates the transition is allowed and records the change in history.
    Facilitators can submit/cancel their own applications.
    Admins/superusers can perform review transitions.
    """
    application = session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _check_application_access(
        session=session, application=application, current_user=current_user
    )

    # Facilitators can only submit or cancel
    if current_user.role == UserRole.facilitator:
        if status_in.new_status not in (
            ApplicationStatus.submitted,
            ApplicationStatus.cancelled,
        ):
            raise HTTPException(
                status_code=403,
                detail="Facilitators can only submit or cancel applications",
            )

    if not crud.is_valid_transition(
        current=application.status, new=status_in.new_status
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{application.status.value}' to '{status_in.new_status.value}'",
        )

    history = crud.create_status_history(
        session=session,
        application=application,
        history_in=status_in,
        changed_by=current_user.id,
    )
    return history


# ---------------------------------------------------------------------------
# Status History listing
# ---------------------------------------------------------------------------


@router.get(
    "/{application_id}/status-history",
    response_model=ApplicationStatusHistoriesPublic,
)
def read_application_status_history(
    application_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Retrieve the status change history for an application."""
    application = session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _check_application_access(
        session=session, application=application, current_user=current_user
    )

    count_statement = (
        select(func.count())
        .select_from(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == application_id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == application_id)
        .order_by(col(ApplicationStatusHistory.changed_at).desc())
        .offset(skip)
        .limit(limit)
    )
    history = session.exec(statement).all()
    return ApplicationStatusHistoriesPublic(data=history, count=count)
