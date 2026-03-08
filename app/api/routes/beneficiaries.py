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
    BeneficiariesPublic,
    Beneficiary,
    BeneficiaryCreate,
    BeneficiaryPublic,
    BeneficiaryUpdate,
    Facilitator,
    Message,
    UserRole,
)

router = APIRouter(prefix="/beneficiaries", tags=["beneficiaries"])


@router.get(
    "/",
    response_model=BeneficiariesPublic,
)
def read_beneficiaries(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Retrieve beneficiaries.

    Facilitators see only their own beneficiaries.
    Admins and superusers see all.
    """
    if current_user.role == UserRole.facilitator:
        facilitator = crud.get_facilitator_by_user_id(
            session=session, user_id=current_user.id
        )
        if not facilitator:
            raise HTTPException(status_code=404, detail="Facilitator profile not found")
        count_statement = (
            select(func.count())
            .select_from(Beneficiary)
            .where(Beneficiary.facilitator_id == facilitator.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Beneficiary)
            .where(Beneficiary.facilitator_id == facilitator.id)
            .order_by(col(Beneficiary.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
    elif current_user.role in (UserRole.admin, UserRole.superuser):
        count_statement = select(func.count()).select_from(Beneficiary)
        count = session.exec(count_statement).one()
        statement = (
            select(Beneficiary)
            .order_by(col(Beneficiary.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
    else:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )

    beneficiaries = session.exec(statement).all()
    return BeneficiariesPublic(data=beneficiaries, count=count)


@router.post(
    "/",
    response_model=BeneficiaryPublic,
)
def create_beneficiary(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    beneficiary_in: BeneficiaryCreate,
) -> Any:
    """Create a new beneficiary.

    Facilitators can only create beneficiaries linked to their own profile.
    Admins and superusers can create for any facilitator.
    """
    # Verify the facilitator exists
    facilitator = session.get(Facilitator, beneficiary_in.facilitator_id)
    if not facilitator:
        raise HTTPException(status_code=404, detail="Facilitator not found")

    # Facilitators can only create beneficiaries for themselves
    if current_user.role == UserRole.facilitator:
        own_facilitator = crud.get_facilitator_by_user_id(
            session=session, user_id=current_user.id
        )
        if not own_facilitator or own_facilitator.id != beneficiary_in.facilitator_id:
            raise HTTPException(
                status_code=403,
                detail="Facilitators can only create beneficiaries for their own profile",
            )
    elif current_user.role not in (UserRole.admin, UserRole.superuser):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )

    # Check for duplicate CURP
    existing = crud.get_beneficiary_by_curp(session=session, curp=beneficiary_in.curp)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A beneficiary with this CURP already exists",
        )

    beneficiary = crud.create_beneficiary(
        session=session, beneficiary_in=beneficiary_in
    )
    return beneficiary


@router.get(
    "/{beneficiary_id}",
    response_model=BeneficiaryPublic,
)
def read_beneficiary_by_id(
    beneficiary_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """Get a specific beneficiary by id.

    Facilitators can only view their own beneficiaries.
    """
    beneficiary = session.get(Beneficiary, beneficiary_id)
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    if current_user.role == UserRole.facilitator:
        own_facilitator = crud.get_facilitator_by_user_id(
            session=session, user_id=current_user.id
        )
        if not own_facilitator or own_facilitator.id != beneficiary.facilitator_id:
            raise HTTPException(
                status_code=403,
                detail="The user doesn't have enough privileges",
            )
    elif current_user.role not in (UserRole.admin, UserRole.superuser):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )

    return beneficiary


@router.patch(
    "/{beneficiary_id}",
    response_model=BeneficiaryPublic,
)
def update_beneficiary(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    beneficiary_id: uuid.UUID,
    beneficiary_in: BeneficiaryUpdate,
) -> Any:
    """Update a beneficiary.

    Facilitators can only update their own beneficiaries.
    """
    beneficiary = session.get(Beneficiary, beneficiary_id)
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    if current_user.role == UserRole.facilitator:
        own_facilitator = crud.get_facilitator_by_user_id(
            session=session, user_id=current_user.id
        )
        if not own_facilitator or own_facilitator.id != beneficiary.facilitator_id:
            raise HTTPException(
                status_code=403,
                detail="The user doesn't have enough privileges",
            )
    elif current_user.role not in (UserRole.admin, UserRole.superuser):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )

    # If CURP is being changed, check for duplicates
    if beneficiary_in.curp and beneficiary_in.curp != beneficiary.curp:
        existing = crud.get_beneficiary_by_curp(
            session=session, curp=beneficiary_in.curp
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="A beneficiary with this CURP already exists",
            )

    beneficiary = crud.update_beneficiary(
        session=session,
        db_beneficiary=beneficiary,
        beneficiary_in=beneficiary_in,
    )
    return beneficiary


@router.delete(
    "/{beneficiary_id}",
    dependencies=[Depends(get_current_admin_or_superuser)],
)
def delete_beneficiary(session: SessionDep, beneficiary_id: uuid.UUID) -> Message:
    """Delete a beneficiary."""
    beneficiary = session.get(Beneficiary, beneficiary_id)
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")
    session.delete(beneficiary)
    session.commit()
    return Message(message="Beneficiary deleted successfully")
