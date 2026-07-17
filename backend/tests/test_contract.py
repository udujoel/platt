import asyncio
from threading import Thread
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.event_bus import event_bus
from app.models import AgentStateEvent, EventType, PlattState


def make_client(tmp_path) -> TestClient:
    return TestClient(create_app(db_path=tmp_path / "platt-test.db"))


def test_health_returns_ok(tmp_path) -> None:
    client = make_client(tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_accepts_job(tmp_path) -> None:
    client = make_client(tmp_path)

    response = client.post("/chat", json={"prompt": "hello"})

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["job_id"]


def test_chat_validation_rejects_empty_prompt(tmp_path) -> None:
    client = make_client(tmp_path)

    response = client.post("/chat", json={"prompt": ""})

    assert response.status_code == 422


def test_dev_state_cycle_accepts_job(tmp_path) -> None:
    client = make_client(tmp_path)

    response = client.post("/dev/state-cycle")

    assert response.status_code == 202
    assert response.json()["status"] == "started"
    assert response.json()["job_id"]


def test_websocket_receives_phase_1_events(tmp_path) -> None:
    client = make_client(tmp_path)
    job_id = uuid4()

    def publish_event() -> None:
        asyncio.run(
            event_bus.publish(
                AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Planning response")
            )
        )

    with client.websocket_connect("/ws") as websocket:
        thread = Thread(target=publish_event)
        thread.start()

        event = websocket.receive_json()
        thread.join(timeout=5)
        assert not thread.is_alive()

        assert event["type"] == EventType.AGENT_STATE
        assert event["job_id"] == str(job_id)
        assert event["state"] == PlattState.THINKING
        assert event["label"] == "Planning response"


def test_chat_job_is_persisted_with_event_and_audit_entry(tmp_path) -> None:
    client = make_client(tmp_path)

    response = client.post("/chat", json={"prompt": "hello persistence"})
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    job = client.get(f"/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["prompt"] == "hello persistence"
    assert job.json()["status"] == "accepted"

    events = client.get(f"/jobs/{job_id}/events")
    assert events.status_code == 200
    assert any(event["type"] == EventType.JOB_CREATED for event in events.json()["events"])

    audit_entries = client.get(f"/audit?job_id={job_id}")
    assert audit_entries.status_code == 200
    assert audit_entries.json()["entries"][0]["action"] == "create_job"
