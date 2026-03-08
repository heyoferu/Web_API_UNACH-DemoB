from cryptography.fernet import Fernet

import app.core.encryption as enc_module
from app.core.encryption import (
    EncryptedString,
    decrypt_value,
    encrypt_value,
    get_fernet,
    init_encryption,
)


def test_init_encryption_and_get_fernet() -> None:
    """init_encryption sets the module-level Fernet instance."""
    original_fernet = enc_module._fernet
    try:
        key = Fernet.generate_key().decode()
        init_encryption(key)
        fernet = get_fernet()
        assert isinstance(fernet, Fernet)
    finally:
        enc_module._fernet = original_fernet


def test_encrypt_decrypt_round_trip() -> None:
    """encrypt_value and decrypt_value are inverse operations."""
    plaintext = "CURP1234567890ABCDEF"
    token = encrypt_value(plaintext)
    assert token != plaintext
    assert decrypt_value(token) == plaintext


def test_encrypt_produces_different_ciphertexts() -> None:
    """Fernet tokens include a timestamp/IV so each call produces a different token."""
    plaintext = "same-value"
    token_a = encrypt_value(plaintext)
    token_b = encrypt_value(plaintext)
    assert token_a != token_b
    assert decrypt_value(token_a) == plaintext
    assert decrypt_value(token_b) == plaintext


def test_encrypt_empty_string() -> None:
    """Encrypting an empty string round-trips correctly."""
    token = encrypt_value("")
    assert decrypt_value(token) == ""


def test_encrypt_unicode() -> None:
    """Unicode characters survive encryption round-trip."""
    plaintext = "Calle Niños Héroes #42, Col. Centro"
    token = encrypt_value(plaintext)
    assert decrypt_value(token) == plaintext


def test_encrypted_string_type_decorator_bind_and_result() -> None:
    """EncryptedString.process_bind_param encrypts, process_result_value decrypts."""
    enc_type = EncryptedString(length=512)
    plaintext = "ABCD123456"

    # Simulate bind (INSERT)
    bound = enc_type.process_bind_param(plaintext, dialect=None)
    assert bound is not None
    assert bound != plaintext

    # Simulate result (SELECT)
    result = enc_type.process_result_value(bound, dialect=None)
    assert result == plaintext


def test_encrypted_string_none_passthrough() -> None:
    """EncryptedString passes None through unchanged."""
    enc_type = EncryptedString(length=512)
    assert enc_type.process_bind_param(None, dialect=None) is None
    assert enc_type.process_result_value(None, dialect=None) is None
