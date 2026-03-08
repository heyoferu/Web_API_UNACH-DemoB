from sqlmodel import Session

from app import crud
from app.models import BeneficiaryCreate, BeneficiaryUpdate, Gender
from tests.utils.beneficiary import random_curp
from tests.utils.facilitator import create_random_facilitator


def test_create_beneficiary(db: Session) -> None:
    _, facilitator = create_random_facilitator(db)
    curp = random_curp()
    beneficiary_in = BeneficiaryCreate(
        curp=curp,
        full_name="María López García",
        date_of_birth=None,
        gender=Gender.female,
        phone="+521234567890",
        address="Calle Reforma #10",
        community="Centro",
        facilitator_id=facilitator.id,
    )
    beneficiary = crud.create_beneficiary(session=db, beneficiary_in=beneficiary_in)

    assert beneficiary.curp == curp
    assert beneficiary.full_name == "María López García"
    assert beneficiary.gender == Gender.female
    assert beneficiary.facilitator_id == facilitator.id
    assert beneficiary.id is not None
    assert beneficiary.is_active is True


def test_update_beneficiary(db: Session) -> None:
    _, facilitator = create_random_facilitator(db)
    curp = random_curp()
    beneficiary_in = BeneficiaryCreate(
        curp=curp,
        full_name="Juan Pérez",
        facilitator_id=facilitator.id,
    )
    beneficiary = crud.create_beneficiary(session=db, beneficiary_in=beneficiary_in)

    update_data = BeneficiaryUpdate(phone="+529999999999", community="Nueva Comunidad")
    updated = crud.update_beneficiary(
        session=db, db_beneficiary=beneficiary, beneficiary_in=update_data
    )

    assert updated.phone == "+529999999999"
    assert updated.community == "Nueva Comunidad"
    assert updated.curp == curp  # unchanged


def test_get_beneficiary_by_curp(db: Session) -> None:
    _, facilitator = create_random_facilitator(db)
    curp = random_curp()
    beneficiary_in = BeneficiaryCreate(
        curp=curp,
        full_name="Carlos Test",
        facilitator_id=facilitator.id,
    )
    crud.create_beneficiary(session=db, beneficiary_in=beneficiary_in)

    found = crud.get_beneficiary_by_curp(session=db, curp=curp)
    assert found is not None
    assert found.curp == curp


def test_get_beneficiary_by_curp_not_found(db: Session) -> None:
    result = crud.get_beneficiary_by_curp(session=db, curp="ZZZZ000000ZZZZZZ99")
    assert result is None


def test_beneficiary_encrypted_fields_round_trip(db: Session) -> None:
    """Verify that encrypted fields (curp, full_name, address) round-trip correctly."""
    _, facilitator = create_random_facilitator(db)
    curp = "LOPG900101HDFRRL09"
    full_name = "Guadalupe López García"
    address = "Av. Niños Héroes #42, Col. Centro, CP 06000"

    beneficiary_in = BeneficiaryCreate(
        curp=curp,
        full_name=full_name,
        address=address,
        facilitator_id=facilitator.id,
    )
    beneficiary = crud.create_beneficiary(session=db, beneficiary_in=beneficiary_in)

    # Re-fetch from DB to ensure decryption works
    db.expire(beneficiary)
    db.refresh(beneficiary)

    assert beneficiary.curp == curp
    assert beneficiary.full_name == full_name
    assert beneficiary.address == address
