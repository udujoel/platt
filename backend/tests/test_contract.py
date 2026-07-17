import asyncio
import sqlite3
from threading import Thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.event_bus import EventBus, event_bus
from app.main import create_app
from app.models import AgentStateEvent, EventType, PlattState
from app.routers.ws import websocket_event_bus


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "platt-test.db")) as test_client:
        yield test_client


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_audit_preflight_allows_local_vite_preview(client: TestClient) -> None:
    response = client.options(
        "/audit",
        headers={
            "Origin": "http://127.0.0.1:5175",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5175"


def test_audit_preflight_rejects_non_local_origin(client: TestClient) -> None:
    response = client.options(
        "/audit",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_chat_accepts_job(client: TestClient) -> None:
    response = client.post("/chat", json={"prompt": "hello"})

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["job_id"]


def test_chat_validation_rejects_empty_prompt(client: TestClient) -> None:
    response = client.post("/chat", json={"prompt": ""})

    assert response.status_code == 422


def test_dev_state_cycle_accepts_job(client: TestClient) -> None:
    response = client.post("/dev/state-cycle")

    assert response.status_code == 202
    assert response.json()["status"] == "started"
    assert response.json()["job_id"]


def test_websocket_receives_phase_1_events(client: TestClient) -> None:
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


def test_chat_job_is_persisted_with_event_and_audit_entry(client: TestClient) -> None:

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


def test_lifespan_closes_persistence_and_clears_event_recorder(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "platt-test.db")

    with TestClient(app) as client:
        persistence = app.state.persistence
        assert client.get("/health").status_code == 200
        assert event_bus._recorder is not None

    assert event_bus._recorder is None
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        persistence.get_job(uuid4())


def test_closing_an_older_app_does_not_clear_the_latest_recorder(tmp_path) -> None:
    first_app = create_app(db_path=tmp_path / "first.db")
    second_app = create_app(db_path=tmp_path / "second.db")
    first_client = TestClient(first_app)
    second_client = TestClient(second_app)
    first_started = False
    second_started = False

    try:
        first_client.__enter__()
        first_started = True
        first_recorder = event_bus._recorder

        second_client.__enter__()
        second_started = True
        second_recorder = event_bus._recorder
        assert second_recorder is not first_recorder

        first_client.__exit__(None, None, None)
        first_started = False
        assert event_bus._recorder is second_recorder
    finally:
        if first_started:
            first_client.__exit__(None, None, None)
        if second_started:
            second_client.__exit__(None, None, None)

    assert event_bus._recorder is None


def test_event_bus_delivers_when_recorder_fails() -> None:
    async def publish_and_receive() -> AgentStateEvent:
        bus = EventBus()
        event = AgentStateEvent(job_id=uuid4(), state=PlattState.THINKING, label="Still deliver")

        def failing_recorder(_: AgentStateEvent) -> None:
            raise sqlite3.ProgrammingError("closed database")

        bus.set_recorder(failing_recorder)

        async def receive_one() -> AgentStateEvent:
            async for received in bus.subscribe():
                return received
            raise AssertionError("Event subscription ended unexpectedly")

        receiver = asyncio.create_task(receive_one())
        await asyncio.sleep(0)
        await bus.publish(event)
        return await receiver

    received = asyncio.run(publish_and_receive())
    assert received.label == "Still deliver"


def test_websocket_delivery_survives_recorder_failure(client: TestClient) -> None:
    job_id = uuid4()
    active_recorder = event_bus._recorder

    def failing_recorder(_: AgentStateEvent) -> None:
        raise sqlite3.ProgrammingError("closed database")

    event_bus.set_recorder(failing_recorder)
    try:
        def publish_event() -> None:
            asyncio.run(
                event_bus.publish(
                    AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Still deliver")
                )
            )

        with client.websocket_connect("/ws") as websocket:
            thread = Thread(target=publish_event)
            thread.start()

            event = websocket.receive_json()
            thread.join(timeout=5)
            assert not thread.is_alive()

        assert event["job_id"] == str(job_id)
        assert event["label"] == "Still deliver"
    finally:
        event_bus.set_recorder(active_recorder)


def test_websocket_cancellation_propagates(monkeypatch) -> None:
    class Websocket:
        async def accept(self) -> None:
            return None

    async def cancelled_subscription():
        raise asyncio.CancelledError
        yield  # pragma: no cover

    monkeypatch.setattr(event_bus, "subscribe", cancelled_subscription)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(websocket_event_bus(Websocket()))


def test_persistence_creates_job_id_indexes(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "platt-test.db")

    with TestClient(app):
        connection = app.state.persistence._connection
        event_indexes = {row[1] for row in connection.execute("pragma index_list(events)")}
        audit_indexes = {row[1] for row in connection.execute("pragma index_list(audit_entries)")}
        event_index_columns = {
            row[2] for row in connection.execute("pragma index_info(idx_events_job_id)")
        }
        audit_index_columns = {
            row[2] for row in connection.execute("pragma index_info(idx_audit_entries_job_id)")
        }

    assert "idx_events_job_id" in event_indexes
    assert "idx_audit_entries_job_id" in audit_indexes
    assert event_index_columns == {"job_id"}
    assert audit_index_columns == {"job_id"}
