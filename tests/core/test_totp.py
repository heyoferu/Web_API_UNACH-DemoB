import pyotp

from app.core.totp import (
    generate_totp_secret,
    get_totp_provisioning_uri,
    verify_totp_code,
)


def test_generate_totp_secret() -> None:
    """Generated secret should be a valid base32 string of standard length."""
    secret = generate_totp_secret()
    assert len(secret) == 32  # pyotp default base32 length
    # Should be decodable as base32
    import base64

    base64.b32decode(secret)


def test_generate_totp_secret_unique() -> None:
    """Each call should produce a different secret."""
    s1 = generate_totp_secret()
    s2 = generate_totp_secret()
    assert s1 != s2


def test_get_totp_provisioning_uri() -> None:
    """Provisioning URI should contain the expected components."""
    secret = generate_totp_secret()
    uri = get_totp_provisioning_uri(
        secret=secret, email="admin@example.com", issuer="Bienestar"
    )
    assert uri.startswith("otpauth://totp/")
    assert "admin%40example.com" in uri or "admin@example.com" in uri
    assert "Bienestar" in uri
    assert f"secret={secret}" in uri


def test_verify_totp_code_valid() -> None:
    """A freshly generated code should verify successfully."""
    secret = generate_totp_secret()
    totp = pyotp.TOTP(secret)
    code = totp.now()
    assert verify_totp_code(secret=secret, code=code) is True


def test_verify_totp_code_invalid() -> None:
    """A wrong code should fail verification."""
    secret = generate_totp_secret()
    assert verify_totp_code(secret=secret, code="000000") is False


def test_verify_totp_code_wrong_secret() -> None:
    """A code generated with a different secret should fail."""
    secret1 = generate_totp_secret()
    secret2 = generate_totp_secret()
    totp = pyotp.TOTP(secret1)
    code = totp.now()
    assert verify_totp_code(secret=secret2, code=code) is False
