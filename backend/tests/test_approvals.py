import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.approvals import (
    ApprovalAlreadyConsumedError,
    ApprovalExpiredError,
    ApprovalNotDecidedError,
    ApprovalNotFoundError,
    BlastRadiusError,
    check_blast_radius,
    consume_approval,
    require_approval,
)
from app.main import create_app
from app.persistence import Persistence


@pytest.fixture
def persistence(tmp_path):
    instance = Persistence(db_path=tmp_path / "platt-approvals-test.db")
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "platt-approvals-api-test.db")) as test_client:
        yield test_client


def _approve(persistence: Persistence, approval_id, ttl_seconds: int = 900) -> None:
    rows = persistence.decide_approval(
        approval_id=approval_id,
        approver="alice",
        status="approved",
        expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
    )
    assert rows == 1


# --- gate blocks without approval -------------------------------------------------


def test_require_approval_blocks_when_no_approval_exists(persistence: Persistence) -> None:
    job_id = uuid4()

    with pytest.raises(ApprovalNotFoundError):
        require_approval(persistence, job_id, plan_hash="hash-a", commit_sha="sha-a")


def test_require_approval_blocks_while_pending(persistence: Persistence) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")

    with pytest.raises(ApprovalNotDecidedError):
        require_approval(persistence, job_id, plan_hash="hash-a", commit_sha="sha-a")


def test_require_approval_blocks_when_rejected(persistence: Persistence) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
    persistence.decide_approval(approval_id, approver="alice", status="rejected", expires_at=None)

    with pytest.raises(ApprovalNotDecidedError):
        require_approval(persistence, job_id, plan_hash="hash-a", commit_sha="sha-a")


def test_require_approval_succeeds_for_exact_match(persistence: Persistence) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
    _approve(persistence, approval_id)

    record = require_approval(persistence, job_id, plan_hash="hash-a", commit_sha="sha-a")

    assert record.id == str(approval_id)
    assert record.status == "approved"


# --- mismatch (plan_hash / commit_sha) rejected ------------------------------------


def test_require_approval_rejects_plan_hash_mismatch(persistence: Persistence) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
    _approve(persistence, approval_id)

    with pytest.raises(ApprovalNotFoundError):
        require_approval(persistence, job_id, plan_hash="hash-b", commit_sha="sha-a")


def test_require_approval_rejects_commit_sha_mismatch(persistence: Persistence) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
    _approve(persistence, approval_id)

    with pytest.raises(ApprovalNotFoundError):
        require_approval(persistence, job_id, plan_hash="hash-a", commit_sha="sha-b")


def test_require_approval_rejects_different_job(persistence: Persistence) -> None:
    job_id = uuid4()
    other_job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
    _approve(persistence, approval_id)

    with pytest.raises(ApprovalNotFoundError):
        require_approval(persistence, other_job_id, plan_hash="hash-a", commit_sha="sha-a")


# --- double-consume fails -----------------------------------------------------------


def test_consume_approval_is_one_time(persistence: Persistence) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
    _approve(persistence, approval_id)

    consume_approval(persistence, approval_id)

    with pytest.raises(ApprovalAlreadyConsumedError):
        consume_approval(persistence, approval_id)


def test_consumed_approval_no_longer_satisfies_require_approval(persistence: Persistence) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
    _approve(persistence, approval_id)
    consume_approval(persistence, approval_id)

    with pytest.raises(ApprovalAlreadyConsumedError):
        require_approval(persistence, job_id, plan_hash="hash-a", commit_sha="sha-a")


# --- expiry blocks -------------------------------------------------------------------


def test_require_approval_blocks_when_expired(persistence: Persistence) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
    persistence.decide_approval(
        approval_id,
        approver="alice",
        status="approved",
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )

    with pytest.raises(ApprovalExpiredError):
        require_approval(persistence, job_id, plan_hash="hash-a", commit_sha="sha-a")


def test_consume_approval_blocks_when_expired(persistence: Persistence) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
    persistence.decide_approval(
        approval_id,
        approver="alice",
        status="approved",
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )

    with pytest.raises(ApprovalExpiredError):
        consume_approval(persistence, approval_id)


# --- blast radius ----------------------------------------------------------------


def test_check_blast_radius_allows_in_sandbox_plan_within_destroy_cap() -> None:
    plan = {
        "resource_changes": [
            {"address": "azurerm_storage_account.sandbox-rg.logs", "change": {"actions": ["create"]}},
            {"address": "azurerm_storage_account.sandbox-rg.old", "change": {"actions": ["delete"]}},
        ]
    }

    check_blast_radius(plan, sandbox_rg="sandbox-rg")


def test_check_blast_radius_blocks_out_of_sandbox_address() -> None:
    plan = {
        "resource_changes": [
            {"address": "azurerm_storage_account.prod-rg.logs", "change": {"actions": ["create"]}},
        ]
    }

    with pytest.raises(BlastRadiusError):
        check_blast_radius(plan, sandbox_rg="sandbox-rg")


def test_check_blast_radius_blocks_more_than_three_destroys() -> None:
    plan = {
        "resource_changes": [
            {"address": f"azurerm_storage_account.sandbox-rg.item{i}", "change": {"actions": ["delete"]}}
            for i in range(4)
        ]
    }

    with pytest.raises(BlastRadiusError):
        check_blast_radius(plan, sandbox_rg="sandbox-rg")


def test_check_blast_radius_allows_exactly_three_destroys() -> None:
    plan = {
        "resource_changes": [
            {"address": f"azurerm_storage_account.sandbox-rg.item{i}", "change": {"actions": ["delete"]}}
            for i in range(3)
        ]
    }

    check_blast_radius(plan, sandbox_rg="sandbox-rg")


# --- router: create / decide / get / events ----------------------------------------


def test_create_decide_get_approval_flow(client: TestClient) -> None:
    job_id = str(uuid4())

    create_response = client.post(
        "/approvals",
        json={
            "job_id": job_id,
            "plan_hash": "hash-a",
            "commit_sha": "sha-a",
            "scope": "sandbox-rg",
            "summary": "Create a storage account",
        },
    )
    assert create_response.status_code == 201
    approval_id = create_response.json()["id"]
    assert create_response.json()["status"] == "pending"

    get_response = client.get(f"/approvals/{approval_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "pending"

    decide_response = client.post(
        f"/approvals/{approval_id}/decide",
        json={"approver": "alice", "decision": "approved"},
    )
    assert decide_response.status_code == 200
    assert decide_response.json()["status"] == "approved"
    assert decide_response.json()["approver"] == "alice"

    list_response = client.get("/approvals", params={"job_id": job_id})
    assert list_response.status_code == 200
    assert len(list_response.json()["approvals"]) == 1


def test_decide_approval_twice_fails(client: TestClient) -> None:
    job_id = str(uuid4())
    approval_id = client.post(
        "/approvals",
        json={"job_id": job_id, "plan_hash": "hash-a", "commit_sha": "sha-a", "scope": "sandbox-rg"},
    ).json()["id"]

    first = client.post(f"/approvals/{approval_id}/decide", json={"approver": "alice", "decision": "approved"})
    assert first.status_code == 200

    second = client.post(f"/approvals/{approval_id}/decide", json={"approver": "bob", "decision": "rejected"})
    assert second.status_code == 409

    # The first, immutable decision must survive the rejected re-decide attempt.
    record = client.get(f"/approvals/{approval_id}").json()
    assert record["status"] == "approved"
    assert record["approver"] == "alice"


def test_get_unknown_approval_returns_404(client: TestClient) -> None:
    response = client.get(f"/approvals/{uuid4()}")
    assert response.status_code == 404


def test_decide_unknown_approval_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/approvals/{uuid4()}/decide", json={"approver": "alice", "decision": "approved"}
    )
    assert response.status_code == 404


def test_create_approval_emits_approval_required_event(client: TestClient) -> None:
    job_id = uuid4()
    approval_id = client.post(
        "/approvals",
        json={"job_id": str(job_id), "plan_hash": "hash-a", "commit_sha": "sha-a", "scope": "sandbox-rg"},
    ).json()["id"]

    events = client.app.state.persistence.list_job_events(job_id)
    types = [event["type"] for event in events]
    assert "approval_required" in types
    approval_required = next(event for event in events if event["type"] == "approval_required")
    assert approval_required["id"]  # sanity: row has a durable event id
    payload = json.loads(approval_required["payload"])
    assert payload["approval_id"] == approval_id


def test_decide_approval_emits_approval_result_event(client: TestClient) -> None:
    job_id = uuid4()
    approval_id = client.post(
        "/approvals",
        json={"job_id": str(job_id), "plan_hash": "hash-a", "commit_sha": "sha-a", "scope": "sandbox-rg"},
    ).json()["id"]

    client.post(f"/approvals/{approval_id}/decide", json={"approver": "alice", "decision": "approved"})

    events = client.app.state.persistence.list_job_events(job_id)
    approval_result = next(event for event in events if event["type"] == "approval_result")
    payload = json.loads(approval_result["payload"])
    assert payload["approval_id"] == approval_id
    assert payload["approved"] is True


def test_full_gate_flow_via_api_then_consume(client: TestClient, persistence: Persistence) -> None:
    """End-to-end: create -> decide -> require_approval succeeds -> consume is one-time."""
    del persistence  # separate db from the client fixture; only used for type clarity
    job_id = str(uuid4())
    approval_id = client.post(
        "/approvals",
        json={"job_id": job_id, "plan_hash": "hash-a", "commit_sha": "sha-a", "scope": "sandbox-rg"},
    ).json()["id"]
    client.post(f"/approvals/{approval_id}/decide", json={"approver": "alice", "decision": "approved"})

    app_persistence = client.app.state.persistence
    record = require_approval(app_persistence, job_id, plan_hash="hash-a", commit_sha="sha-a")
    assert record.status == "approved"

    consume_approval(app_persistence, approval_id)
    with pytest.raises(ApprovalAlreadyConsumedError):
        consume_approval(app_persistence, approval_id)
