"""HMAC-SHA256 integrity verification for audit log entries.

Each audit log record stores an ``integrity_hash`` computed over a canonical
string representation of the record's key fields.  This allows downstream
consumers (or a periodic integrity check job) to verify that the row has not
been tampered with after creation.

The HMAC key is the application's ``SECRET_KEY``.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime


def compute_integrity_hash(
    *,
    secret_key: str,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    user_id: uuid.UUID,
    created_at: datetime,
) -> str:
    """Compute an HMAC-SHA256 hex digest for an audit log entry.

    The canonical message is built by concatenating the fields with ``|`` as
    separator.  All UUID and datetime values are converted to their ISO-8601
    string representation to guarantee deterministic reproduction.
    """
    message = "|".join(
        [
            action,
            resource_type,
            str(resource_id),
            str(user_id),
            created_at.isoformat(),
        ]
    )
    return hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_integrity_hash(
    *,
    secret_key: str,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    user_id: uuid.UUID,
    created_at: datetime,
    integrity_hash: str,
) -> bool:
    """Verify an audit log entry's integrity hash.

    Returns ``True`` if the stored hash matches the recomputed one.
    Uses ``hmac.compare_digest`` for constant-time comparison.
    """
    expected = compute_integrity_hash(
        secret_key=secret_key,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        created_at=created_at,
    )
    return hmac.compare_digest(expected, integrity_hash)
