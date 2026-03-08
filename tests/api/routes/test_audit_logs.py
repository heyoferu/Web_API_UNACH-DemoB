import uuid

from fastapi.testclient import TestClient

from app.core.config import settings

# ---------------------------------------------------------------------------
# List audit logs
# ---------------------------------------------------------------------------


def test_read_audit_logs_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/audit-logs/",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert "count" in data


def test_read_audit_logs_as_facilitator_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/audit-logs/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Create audit log
# ---------------------------------------------------------------------------


def test_create_audit_log(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    resource_id = str(uuid.uuid4())
    r = client.post(
        f"{settings.API_V1_STR}/audit-logs/",
        headers=superuser_token_headers,
        json={
            "action": "test.action",
            "resource_type": "test_resource",
            "resource_id": resource_id,
            "details": "A test audit log entry",
            "ip_address": "127.0.0.1",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "test.action"
    assert data["resource_type"] == "test_resource"
    assert data["resource_id"] == resource_id
    assert data["integrity_hash"] is not None
    assert len(data["integrity_hash"]) == 64


# ---------------------------------------------------------------------------
# Read audit log by ID
# ---------------------------------------------------------------------------


def test_read_audit_log_by_id(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # Create one first
    resource_id = str(uuid.uuid4())
    r = client.post(
        f"{settings.API_V1_STR}/audit-logs/",
        headers=superuser_token_headers,
        json={
            "action": "read.test",
            "resource_type": "test",
            "resource_id": resource_id,
        },
    )
    audit_log_id = r.json()["id"]
    r = client.get(
        f"{settings.API_V1_STR}/audit-logs/{audit_log_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == audit_log_id


def test_read_audit_log_by_id_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/audit-logs/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Verify audit log integrity
# ---------------------------------------------------------------------------


def test_verify_audit_log_integrity_valid(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    resource_id = str(uuid.uuid4())
    r = client.post(
        f"{settings.API_V1_STR}/audit-logs/",
        headers=superuser_token_headers,
        json={
            "action": "verify.test",
            "resource_type": "test",
            "resource_id": resource_id,
        },
    )
    audit_log_id = r.json()["id"]
    r = client.get(
        f"{settings.API_V1_STR}/audit-logs/{audit_log_id}/verify",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["integrity_valid"] is True
    assert data["audit_log_id"] == audit_log_id


def test_verify_audit_log_integrity_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/audit-logs/{uuid.uuid4()}/verify",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
