import asyncio
from threading import Thread
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.event_bus import event_bus
from app.models import AgentStateEvent, EventType, PlattState


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_accepts_job() -> None:
    client = TestClient(create_app())

    response = client.post("/chat", json={"prompt": "hello"})

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["job_id"]


def test_chat_validation_rejects_empty_prompt() -> None:
    client = TestClient(create_app())

    response = client.post("/chat", json={"prompt": ""})

    assert response.status_code == 422


def test_websocket_receives_phase_1_events() -> None:
    client = TestClient(create_app())
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
