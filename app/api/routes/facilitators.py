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
    Facilitator,
    FacilitatorCreate,
    FacilitatorPublic,
    FacilitatorsPublic,
    FacilitatorUpdate,
    Message,
    User,
    UserRole,
)

router = APIRouter(prefix="/facilitators", tags=["facilitators"])


@router.get(
    "/",
    dependencies=[Depends(get_current_admin_or_superuser)],
    response_model=FacilitatorsPublic,
)
def read_facilitators(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """Retrieve facilitators."""
    count_statement = select(func.count()).select_from(Facilitator)
    count = session.exec(count_statement).one()

    statement = (
        select(Facilitator)
        .order_by(col(Facilitator.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    facilitators = session.exec(statement).all()

    return FacilitatorsPublic(data=facilitators, count=count)


@router.post(
    "/",
    dependencies=[Depends(get_current_admin_or_superuser)],
    response_model=FacilitatorPublic,
)
def create_facilitator(
    *, session: SessionDep, facilitator_in: FacilitatorCreate
) -> Any:
    """Create a new facilitator profile.

    The target user must exist and have the facilitator role.
    """
    # Verify the user exists
    db_user = session.get(User, facilitator_in.user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify the user has the facilitator role
    if db_user.role != UserRole.facilitator:
        raise HTTPException(
            status_code=400,
            detail="User must have the facilitator role to create a facilitator profile",
        )

    # Check if a profile already exists for this user
    existing = crud.get_facilitator_by_user_id(
        session=session, user_id=facilitator_in.user_id
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A facilitator profile already exists for this user",
        )

    facilitator = crud.create_facilitator(
        session=session, facilitator_in=facilitator_in
    )
    return facilitator


@router.get("/me", response_model=FacilitatorPublic)
def read_facilitator_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """Get the current user's facilitator profile."""
    if current_user.role != UserRole.facilitator:
        raise HTTPException(
            status_code=400,
            detail="Current user does not have a facilitator role",
        )
    facilitator = crud.get_facilitator_by_user_id(
        session=session, user_id=current_user.id
    )
    if not facilitator:
        raise HTTPException(status_code=404, detail="Facilitator profile not found")
    return facilitator


@router.patch("/me", response_model=FacilitatorPublic)
def update_facilitator_me(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    facilitator_in: FacilitatorUpdate,
) -> Any:
    """Update the current user's facilitator profile."""
    if current_user.role != UserRole.facilitator:
        raise HTTPException(
            status_code=400,
            detail="Current user does not have a facilitator role",
        )
    facilitator = crud.get_facilitator_by_user_id(
        session=session, user_id=current_user.id
    )
    if not facilitator:
        raise HTTPException(status_code=404, detail="Facilitator profile not found")
    facilitator = crud.update_facilitator(
        session=session,
        db_facilitator=facilitator,
        facilitator_in=facilitator_in,
    )
    return facilitator


@router.get(
    "/{facilitator_id}",
    dependencies=[Depends(get_current_admin_or_superuser)],
    response_model=FacilitatorPublic,
)
def read_facilitator_by_id(facilitator_id: uuid.UUID, session: SessionDep) -> Any:
    """Get a specific facilitator by id."""
    facilitator = session.get(Facilitator, facilitator_id)
    if not facilitator:
        raise HTTPException(status_code=404, detail="Facilitator not found")
    return facilitator


@router.patch(
    "/{facilitator_id}",
    dependencies=[Depends(get_current_admin_or_superuser)],
    response_model=FacilitatorPublic,
)
def update_facilitator(
    *,
    session: SessionDep,
    facilitator_id: uuid.UUID,
    facilitator_in: FacilitatorUpdate,
) -> Any:
    """Update a facilitator profile."""
    facilitator = session.get(Facilitator, facilitator_id)
    if not facilitator:
        raise HTTPException(status_code=404, detail="Facilitator not found")
    facilitator = crud.update_facilitator(
        session=session,
        db_facilitator=facilitator,
        facilitator_in=facilitator_in,
    )
    return facilitator


@router.delete(
    "/{facilitator_id}",
    dependencies=[Depends(get_current_admin_or_superuser)],
)
def delete_facilitator(session: SessionDep, facilitator_id: uuid.UUID) -> Message:
    """Delete a facilitator profile."""
    facilitator = session.get(Facilitator, facilitator_id)
    if not facilitator:
        raise HTTPException(status_code=404, detail="Facilitator not found")
    session.delete(facilitator)
    session.commit()
    return Message(message="Facilitator deleted successfully")
