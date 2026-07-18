import asyncio
import sqlite3
from threading import Event as ThreadEvent
from threading import Thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.event_bus import EventBus, event_bus
from app.main import create_app
from app.models import AgentStateEvent, EventType, PlattState
from app.routers import dev
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
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5175"
    assert response.headers["access-control-allow-methods"] == "GET, POST"
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers


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


def test_lifespan_cancels_and_drains_app_background_tasks(tmp_path, monkeypatch) -> None:
    app = create_app(db_path=tmp_path / "platt-test.db")
    started = ThreadEvent()
    cancelled = ThreadEvent()

    async def wait_until_cancelled(**_kwargs) -> None:
        try:
            started.set()
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(dev, "stream_dev_state_cycle", wait_until_cancelled)
    with TestClient(app) as client:
        response = client.post("/dev/state-cycle")
        assert response.status_code == 202
        assert started.wait(timeout=1)
        task = next(iter(app.state.background_tasks))
        assert task in app.state.background_tasks

    assert task.cancelled()
    assert cancelled.is_set()
    assert not app.state.background_tasks


def test_background_task_exceptions_are_observed(tmp_path, monkeypatch, caplog) -> None:
    app = create_app(db_path=tmp_path / "platt-test.db")
    failed = ThreadEvent()

    async def fail(**_kwargs) -> None:
        failed.set()
        raise RuntimeError("job failure")

    monkeypatch.setattr(dev, "stream_dev_state_cycle", fail)
    with TestClient(app) as client:
        with caplog.at_level("ERROR"):
            response = client.post("/dev/state-cycle")
            assert response.status_code == 202
            assert failed.wait(timeout=1)

    assert "Background task failed" in caplog.text


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


def test_event_bus_removes_closed_foreign_subscriber_and_delivers_to_live_ones() -> None:
    # The local import keeps this white-box regression test focused on the
    # subscriber state that can only arise after a foreign websocket loop exits.
    from app.event_bus import _Subscriber

    async def publish_to_live_subscriber() -> None:
        bus = EventBus()
        closed_loop = asyncio.new_event_loop()
        closed_loop.close()
        stale_subscriber = _Subscriber(loop=closed_loop, queue=asyncio.Queue(maxsize=1))
        live_subscriber = _Subscriber(loop=asyncio.get_running_loop(), queue=asyncio.Queue(maxsize=1))
        bus._subscribers.update({stale_subscriber, live_subscriber})

        event = AgentStateEvent(job_id=uuid4(), state=PlattState.THINKING, label="Still deliver")
        await bus.publish(event)

        assert await live_subscriber.queue.get() == event
        assert stale_subscriber not in bus._subscribers

    asyncio.run(publish_to_live_subscriber())


def test_event_bus_drops_new_events_when_a_subscriber_queue_is_full() -> None:
    from app.event_bus import _Subscriber

    async def publish_to_full_queue() -> None:
        bus = EventBus(subscriber_queue_size=1)
        subscriber = _Subscriber(loop=asyncio.get_running_loop(), queue=asyncio.Queue(maxsize=1))
        bus._subscribers.add(subscriber)
        first_event = AgentStateEvent(job_id=uuid4(), state=PlattState.THINKING, label="First")
        dropped_event = AgentStateEvent(job_id=uuid4(), state=PlattState.THINKING, label="Dropped")

        await bus.publish(first_event)
        await bus.publish(dropped_event)

        assert subscriber.queue.qsize() == 1
        assert await subscriber.queue.get() == first_event

    asyncio.run(publish_to_full_queue())


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


def test_websocket_send_race_with_closed_transport_is_a_normal_disconnect(monkeypatch) -> None:
    class Websocket:
        accepted = False

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, _event: dict[str, object]) -> None:
            raise RuntimeError("Unable to perform operation on closed transport")

    subscription_closed = False

    async def one_event_subscription():
        nonlocal subscription_closed
        try:
            yield AgentStateEvent(
                job_id=uuid4(), state=PlattState.THINKING, label="Deliver once"
            )
        finally:
            subscription_closed = True

    websocket = Websocket()
    monkeypatch.setattr(event_bus, "subscribe", one_event_subscription)

    asyncio.run(websocket_event_bus(websocket))

    assert websocket.accepted
    assert subscription_closed


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
