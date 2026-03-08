"""TOTP (Time-based One-Time Password) helpers for MFA.

Uses ``pyotp`` to generate and verify 6-digit TOTP codes that rotate every
30 seconds (RFC 6238 defaults).
"""

import pyotp


def generate_totp_secret() -> str:
    """Generate a new random base32 TOTP secret."""
    return pyotp.random_base32()


def get_totp_provisioning_uri(*, secret: str, email: str, issuer: str) -> str:
    """Build an ``otpauth://`` URI suitable for QR code scanning.

    Parameters
    ----------
    secret:
        Base32-encoded TOTP secret.
    email:
        Account identifier shown in authenticator apps.
    issuer:
        Issuer name shown in authenticator apps.
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_totp_code(*, secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code against the given secret.

    Allows a ±1 time-step window (``valid_window=1``) to accommodate minor
    clock drift between the server and the authenticator app.
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
