"""AES-256 column-level encryption for SQLAlchemy / SQLModel.

Provides an ``EncryptedString`` SQLAlchemy custom type that transparently
encrypts values before INSERT/UPDATE and decrypts on SELECT using
`Fernet <https://cryptography.io/en/latest/fernet/>`_ (AES-128-CBC under the
hood with HMAC-SHA256 authentication).  Fernet was chosen over raw AES-256-GCM
for its simplicity, built-in authentication, and key-rotation support via
``MultiFernet``.

Usage in a SQLModel table::

    class Beneficiary(SQLModel, table=True):
        curp: str = Field(
            sa_column=Column(EncryptedString(length=512), nullable=False),
        )
"""

from __future__ import annotations

from cryptography.fernet import Fernet
from sqlalchemy import String, TypeDecorator

# ---------------------------------------------------------------------------
# Module-level Fernet instance — initialised lazily by ``init_encryption()``.
# ---------------------------------------------------------------------------
_fernet: Fernet | None = None


def init_encryption(key: str) -> None:
    """Initialise the module-level Fernet cipher with the given key.

    Must be called once at application startup (before any DB operation that
    touches encrypted columns).  The *key* must be a URL-safe base64-encoded
    32-byte key as produced by ``Fernet.generate_key()``.
    """
    global _fernet  # noqa: PLW0603
    _fernet = Fernet(key.encode() if isinstance(key, str) else key)


def get_fernet() -> Fernet:
    """Return the initialised Fernet instance or raise."""
    if _fernet is None:
        raise RuntimeError(
            "Encryption not initialised. Call init_encryption() at startup."
        )
    return _fernet


def encrypt_value(plain: str) -> str:
    """Encrypt a plaintext string and return a base64 token."""
    return get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token and return the original plaintext."""
    return get_fernet().decrypt(token.encode()).decode()


# ---------------------------------------------------------------------------
# SQLAlchemy custom type
# ---------------------------------------------------------------------------


class EncryptedString(TypeDecorator[str]):
    """A ``VARCHAR`` column that stores Fernet-encrypted ciphertext.

    * On **bind** (INSERT / UPDATE): encrypts the Python value.
    * On **result** (SELECT): decrypts the stored ciphertext.

    The *length* should be large enough to hold the base64-encoded ciphertext.
    A safe rule of thumb is ``len(Fernet.encrypt(b"x" * max_plain_len))``
    which is roughly ``max_plain_len * 1.5 + 100``.
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 512) -> None:
        super().__init__()
        self.impl = String(length)  # type: ignore[assignment]

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return decrypt_value(value)
