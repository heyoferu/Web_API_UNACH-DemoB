import uuid
from datetime import datetime, timezone

from app.core.config import settings
from app.core.integrity import compute_integrity_hash, verify_integrity_hash


def test_compute_integrity_hash_deterministic() -> None:
    """The same inputs always produce the same hash."""
    kwargs = {
        "secret_key": "test-secret",
        "action": "application.approve",
        "resource_type": "application",
        "resource_id": uuid.UUID("12345678-1234-1234-1234-123456789abc"),
        "user_id": uuid.UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef"),
        "created_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    }
    h1 = compute_integrity_hash(**kwargs)
    h2 = compute_integrity_hash(**kwargs)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_compute_integrity_hash_changes_with_action() -> None:
    """Changing action yields a different hash."""
    common = {
        "secret_key": "test-secret",
        "resource_type": "application",
        "resource_id": uuid.UUID("12345678-1234-1234-1234-123456789abc"),
        "user_id": uuid.UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef"),
        "created_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    }
    h1 = compute_integrity_hash(action="application.approve", **common)
    h2 = compute_integrity_hash(action="application.reject", **common)
    assert h1 != h2


def test_compute_integrity_hash_changes_with_key() -> None:
    """Changing the secret key yields a different hash."""
    common = {
        "action": "application.approve",
        "resource_type": "application",
        "resource_id": uuid.UUID("12345678-1234-1234-1234-123456789abc"),
        "user_id": uuid.UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef"),
        "created_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    }
    h1 = compute_integrity_hash(secret_key="key-a", **common)
    h2 = compute_integrity_hash(secret_key="key-b", **common)
    assert h1 != h2


def test_verify_integrity_hash_valid() -> None:
    """verify_integrity_hash returns True for a valid hash."""
    kwargs = {
        "secret_key": "test-secret",
        "action": "user.create",
        "resource_type": "user",
        "resource_id": uuid.UUID("12345678-1234-1234-1234-123456789abc"),
        "user_id": uuid.UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef"),
        "created_at": datetime(2026, 6, 15, 8, 30, 0, tzinfo=timezone.utc),
    }
    h = compute_integrity_hash(**kwargs)
    assert verify_integrity_hash(integrity_hash=h, **kwargs) is True


def test_verify_integrity_hash_invalid() -> None:
    """verify_integrity_hash returns False for a tampered hash."""
    kwargs = {
        "secret_key": "test-secret",
        "action": "user.create",
        "resource_type": "user",
        "resource_id": uuid.UUID("12345678-1234-1234-1234-123456789abc"),
        "user_id": uuid.UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef"),
        "created_at": datetime(2026, 6, 15, 8, 30, 0, tzinfo=timezone.utc),
    }
    assert verify_integrity_hash(integrity_hash="tampered_hash", **kwargs) is False


def test_verify_integrity_hash_with_app_secret_key() -> None:
    """Integration test using the actual app SECRET_KEY."""
    kwargs = {
        "secret_key": settings.SECRET_KEY,
        "action": "beneficiary.update",
        "resource_type": "beneficiary",
        "resource_id": uuid.UUID("11111111-2222-3333-4444-555555555555"),
        "user_id": uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        "created_at": datetime(2026, 3, 7, 10, 0, 0, tzinfo=timezone.utc),
    }
    h = compute_integrity_hash(**kwargs)
    assert verify_integrity_hash(integrity_hash=h, **kwargs) is True
