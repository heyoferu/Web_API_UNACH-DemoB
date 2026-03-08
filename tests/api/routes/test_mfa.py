import pyotp
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import AdminUser, UserCreate, UserRole, UserUpdate
from tests.utils.admin_user import create_random_admin_user
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string, random_username


def _admin_auth_headers(
    client: TestClient, db: Session
) -> tuple[dict[str, str], AdminUser]:
    """Create an admin user with a known password and return auth headers + admin."""
    password = random_lower_string()
    user, admin_user = create_random_admin_user(db)
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=password))
    headers = user_authentication_headers(
        client=client, email=user.email, password=password
    )
    return headers, admin_user


# ---------------------------------------------------------------------------
# MFA Setup
# ---------------------------------------------------------------------------


def test_mfa_setup(client: TestClient, db: Session) -> None:
    """Admin can initiate MFA setup and receive a secret + provisioning URI."""
    headers, _ = _admin_auth_headers(client, db)
    r = client.post(
        f"{settings.API_V1_STR}/admin-users/me/mfa/setup",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "secret" in data
    assert "provisioning_uri" in data
    assert data["provisioning_uri"].startswith("otpauth://totp/")
    assert len(data["secret"]) == 32


def test_mfa_setup_already_enabled(client: TestClient, db: Session) -> None:
    """Cannot setup MFA if it is already enabled."""
    headers, admin_user = _admin_auth_headers(client, db)

    # Enable MFA directly
    secret = pyotp.random_base32()
    admin_user.mfa_secret = secret
    admin_user.mfa_enabled = True
    db.add(admin_user)
    db.commit()

    r = client.post(
        f"{settings.API_V1_STR}/admin-users/me/mfa/setup",
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "MFA is already enabled"


def test_mfa_setup_facilitator_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Facilitator users cannot access MFA setup."""
    r = client.post(
        f"{settings.API_V1_STR}/admin-users/me/mfa/setup",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# MFA Verify Setup
# ---------------------------------------------------------------------------


def test_mfa_verify_setup(client: TestClient, db: Session) -> None:
    """Verifying a valid TOTP code enables MFA."""
    headers, admin_user = _admin_auth_headers(client, db)

    # Setup MFA first
    r = client.post(
        f"{settings.API_V1_STR}/admin-users/me/mfa/setup",
        headers=headers,
    )
    assert r.status_code == 200
    secret = r.json()["secret"]

    # Generate a valid code
    totp = pyotp.TOTP(secret)
    code = totp.now()

    r = client.post(
        f"{settings.API_V1_STR}/admin-users/me/mfa/verify-setup",
        headers=headers,
        json={"code": code},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "MFA enabled successfully"

    # Verify in DB
    db.refresh(admin_user)
    assert admin_user.mfa_enabled is True


def test_mfa_verify_setup_invalid_code(client: TestClient, db: Session) -> None:
    """Invalid TOTP code should fail verification."""
    headers, _ = _admin_auth_headers(client, db)

    # Setup MFA first
    r = client.post(
        f"{settings.API_V1_STR}/admin-users/me/mfa/setup",
        headers=headers,
    )
    assert r.status_code == 200

    r = client.post(
        f"{settings.API_V1_STR}/admin-users/me/mfa/verify-setup",
        headers=headers,
        json={"code": "000000"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid TOTP code"


def test_mfa_verify_setup_no_setup(client: TestClient, db: Session) -> None:
    """Cannot verify setup if setup was never initiated."""
    headers, _ = _admin_auth_headers(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/admin-users/me/mfa/verify-setup",
        headers=headers,
        json={"code": "123456"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# MFA Disable
# ---------------------------------------------------------------------------


def test_mfa_disable(client: TestClient, db: Session) -> None:
    """Admin can disable MFA with a valid TOTP code."""
    headers, admin_user = _admin_auth_headers(client, db)

    # Enable MFA directly
    secret = pyotp.random_base32()
    admin_user.mfa_secret = secret
    admin_user.mfa_enabled = True
    db.add(admin_user)
    db.commit()

    totp = pyotp.TOTP(secret)
    code = totp.now()

    r = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/admin-users/me/mfa",
        headers=headers,
        json={"code": code},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "MFA disabled successfully"

    db.refresh(admin_user)
    assert admin_user.mfa_enabled is False
    assert admin_user.mfa_secret is None


def test_mfa_disable_invalid_code(client: TestClient, db: Session) -> None:
    """Cannot disable MFA with an invalid TOTP code."""
    headers, admin_user = _admin_auth_headers(client, db)

    secret = pyotp.random_base32()
    admin_user.mfa_secret = secret
    admin_user.mfa_enabled = True
    db.add(admin_user)
    db.commit()

    r = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/admin-users/me/mfa",
        headers=headers,
        json={"code": "000000"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid TOTP code"


def test_mfa_disable_not_enabled(client: TestClient, db: Session) -> None:
    """Cannot disable MFA if it is not enabled."""
    headers, _ = _admin_auth_headers(client, db)

    r = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/admin-users/me/mfa",
        headers=headers,
        json={"code": "123456"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "MFA is not enabled"


# ---------------------------------------------------------------------------
# MFA Login Flow
# ---------------------------------------------------------------------------


def test_login_with_mfa_returns_pending_token(client: TestClient, db: Session) -> None:
    """Login for an MFA-enabled admin returns a short-lived pending token."""
    password = random_lower_string()
    user_in = UserCreate(
        email=random_email(),
        password=password,
        username=random_username(),
        role=UserRole.admin,
    )
    user = crud.create_user(session=db, user_create=user_in)

    from app.models import AdminRole, AdminUserCreate

    admin_user_in = AdminUserCreate(
        user_id=user.id,
        admin_role=AdminRole.document_validator,
    )
    admin_user = crud.create_admin_user(session=db, admin_user_in=admin_user_in)

    # Enable MFA
    secret = pyotp.random_base32()
    admin_user.mfa_secret = secret
    admin_user.mfa_enabled = True
    db.add(admin_user)
    db.commit()

    # Login
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": user.email, "password": password},
    )
    assert r.status_code == 200
    token_data = r.json()
    assert "access_token" in token_data

    # The pending token should NOT work for admin routes
    r2 = client.get(
        f"{settings.API_V1_STR}/admin-users/",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert r2.status_code == 403
    assert r2.json()["detail"] == "MFA verification required"


def test_mfa_verify_login(client: TestClient, db: Session) -> None:
    """Full MFA login: password → pending token → TOTP verify → full token."""
    password = random_lower_string()
    user_in = UserCreate(
        email=random_email(),
        password=password,
        username=random_username(),
        role=UserRole.admin,
    )
    user = crud.create_user(session=db, user_create=user_in)

    from app.models import AdminRole, AdminUserCreate

    admin_user_in = AdminUserCreate(
        user_id=user.id,
        admin_role=AdminRole.document_validator,
    )
    admin_user = crud.create_admin_user(session=db, admin_user_in=admin_user_in)

    secret = pyotp.random_base32()
    admin_user.mfa_secret = secret
    admin_user.mfa_enabled = True
    db.add(admin_user)
    db.commit()

    # Step 1: Password login → pending token
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": user.email, "password": password},
    )
    assert r.status_code == 200
    pending_token = r.json()["access_token"]

    # Step 2: TOTP verify → full token
    totp = pyotp.TOTP(secret)
    code = totp.now()
    r = client.post(
        f"{settings.API_V1_STR}/login/mfa-verify",
        json={"mfa_token": pending_token, "code": code},
    )
    assert r.status_code == 200
    full_token = r.json()["access_token"]

    # Step 3: Full token should work for admin routes
    r = client.get(
        f"{settings.API_V1_STR}/admin-users/",
        headers={"Authorization": f"Bearer {full_token}"},
    )
    assert r.status_code == 200


def test_mfa_verify_login_invalid_code(client: TestClient, db: Session) -> None:
    """MFA verify with wrong TOTP code should fail."""
    password = random_lower_string()
    user_in = UserCreate(
        email=random_email(),
        password=password,
        username=random_username(),
        role=UserRole.admin,
    )
    user = crud.create_user(session=db, user_create=user_in)

    from app.models import AdminRole, AdminUserCreate

    admin_user_in = AdminUserCreate(
        user_id=user.id,
        admin_role=AdminRole.document_validator,
    )
    admin_user = crud.create_admin_user(session=db, admin_user_in=admin_user_in)

    secret = pyotp.random_base32()
    admin_user.mfa_secret = secret
    admin_user.mfa_enabled = True
    db.add(admin_user)
    db.commit()

    # Get pending token
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": user.email, "password": password},
    )
    pending_token = r.json()["access_token"]

    # Try with wrong code
    r = client.post(
        f"{settings.API_V1_STR}/login/mfa-verify",
        json={"mfa_token": pending_token, "code": "000000"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid TOTP code"


def test_mfa_verify_login_invalid_token(client: TestClient) -> None:
    """MFA verify with an invalid token should fail."""
    r = client.post(
        f"{settings.API_V1_STR}/login/mfa-verify",
        json={"mfa_token": "invalid-jwt-token", "code": "123456"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid or expired MFA token"


def test_login_without_mfa_returns_full_token(client: TestClient, db: Session) -> None:
    """Login for an admin without MFA returns a normal full token."""
    password = random_lower_string()
    user, _ = create_random_admin_user(db)
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=password))

    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": user.email, "password": password},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    # Should work for admin routes (no MFA required since MFA not enabled)
    r = client.get(
        f"{settings.API_V1_STR}/admin-users/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


def test_mfa_verify_already_verified_token(client: TestClient, db: Session) -> None:
    """Attempting to MFA-verify an already-verified token should fail."""
    password = random_lower_string()
    user_in = UserCreate(
        email=random_email(),
        password=password,
        username=random_username(),
        role=UserRole.admin,
    )
    user = crud.create_user(session=db, user_create=user_in)

    from app.models import AdminRole, AdminUserCreate

    admin_user_in = AdminUserCreate(
        user_id=user.id,
        admin_role=AdminRole.document_validator,
    )
    admin_user = crud.create_admin_user(session=db, admin_user_in=admin_user_in)

    secret = pyotp.random_base32()
    admin_user.mfa_secret = secret
    admin_user.mfa_enabled = True
    db.add(admin_user)
    db.commit()

    # Get pending token and verify it
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": user.email, "password": password},
    )
    pending_token = r.json()["access_token"]

    totp = pyotp.TOTP(secret)
    code = totp.now()
    r = client.post(
        f"{settings.API_V1_STR}/login/mfa-verify",
        json={"mfa_token": pending_token, "code": code},
    )
    assert r.status_code == 200
    full_token = r.json()["access_token"]

    # Try to verify again with the full token
    r = client.post(
        f"{settings.API_V1_STR}/login/mfa-verify",
        json={"mfa_token": full_token, "code": code},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Token is already MFA-verified"
