import random
import string

from sqlmodel import Session

from app import crud
from app.models import (
    Beneficiary,
    BeneficiaryCreate,
    Facilitator,
)


def random_curp() -> str:
    """Generate a random 18-character CURP-like string."""
    letters = string.ascii_uppercase
    digits = string.digits
    return "".join(
        random.choices(letters, k=4)
        + random.choices(digits, k=6)
        + random.choices(letters, k=6)
        + random.choices(digits, k=2)
    )


def create_random_beneficiary(db: Session, *, facilitator: Facilitator) -> Beneficiary:
    """Create a random beneficiary linked to the given facilitator."""
    beneficiary_in = BeneficiaryCreate(
        curp=random_curp(),
        full_name="Test Beneficiary "
        + "".join(random.choices(string.ascii_lowercase, k=6)),
        date_of_birth=None,
        gender=None,
        phone="+5200000000001",
        address="Calle Test #1",
        community="Comunidad Test",
        facilitator_id=facilitator.id,
    )
    return crud.create_beneficiary(session=db, beneficiary_in=beneficiary_in)
