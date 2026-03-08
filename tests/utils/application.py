import random
import string

from sqlmodel import Session

from app import crud
from app.models import (
    Application,
    ApplicationCreate,
    Beneficiary,
)


def create_random_application(db: Session, *, beneficiary: Beneficiary) -> Application:
    """Create a random application linked to the given beneficiary."""
    program_name = "Programa " + "".join(random.choices(string.ascii_lowercase, k=6))
    application_in = ApplicationCreate(
        program_name=program_name,
        description="Test application description",
        beneficiary_id=beneficiary.id,
    )
    return crud.create_application(session=db, application_in=application_in)
