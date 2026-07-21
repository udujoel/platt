import asyncio
import json
import time
from datetime import datetime, timezone
from threading import Thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.event_bus import event_bus
from app.main import create_app
from app.models import AgentStateEvent, EventType, PlattState


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "platt-test.db")) as test_client:
        yield test_client


def _parse_sse_frames(body: str) -> list[dict[str, str]]:
    frames = []
    for chunk in body.strip("\n").split("\n\n"):
        if not chunk.strip():
            continue
        frame: dict[str, str] = {}
        for line in chunk.split("\n"):
            key, _, value = line.partition(": ")
            frame[key] = value
        frames.append(frame)
    return frames


def test_sse_stream_frames_backfilled_events_with_id_event_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLATT_SSE_MAX_SECONDS", "0.3")
    persistence = client.app.state.persistence
    job_id = uuid4()
    created_at = datetime(2026, 7, 18, 1, 0, tzinfo=timezone.utc)
    event = AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Backfilled", created_at=created_at)
    persistence.record_event(event)
    seq = persistence.get_event_seq(event.id)

    with client.stream("GET", "/events/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    frames = _parse_sse_frames(body)
    assert len(frames) == 1
    assert frames[0]["id"] == str(seq)
    assert frames[0]["event"] == EventType.AGENT_STATE
    assert json.loads(frames[0]["data"]) == json.loads(event.model_dump_json())


def test_sse_stream_resumes_from_last_event_id_via_events_table(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLATT_SSE_MAX_SECONDS", "0.3")
    persistence = client.app.state.persistence
    job_id = uuid4()
    created_at = datetime(2026, 7, 18, 1, 0, tzinfo=timezone.utc)
    first = AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="First", created_at=created_at)
    second = AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Second", created_at=created_at)
    persistence.record_event(first)
    persistence.record_event(second)
    first_seq = persistence.get_event_seq(first.id)
    second_seq = persistence.get_event_seq(second.id)

    with client.stream("GET", "/events/stream", headers={"Last-Event-ID": str(first_seq)}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    frames = _parse_sse_frames(body)
    assert len(frames) == 1
    assert frames[0]["id"] == str(second_seq)
    assert json.loads(frames[0]["data"])["label"] == "Second"


def test_sse_stream_filters_backfill_by_job_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATT_SSE_MAX_SECONDS", "0.3")
    persistence = client.app.state.persistence
    wanted_job_id = uuid4()
    other_job_id = uuid4()
    created_at = datetime(2026, 7, 18, 1, 0, tzinfo=timezone.utc)
    wanted = AgentStateEvent(job_id=wanted_job_id, state=PlattState.THINKING, label="Wanted", created_at=created_at)
    other = AgentStateEvent(job_id=other_job_id, state=PlattState.THINKING, label="Other", created_at=created_at)
    persistence.record_event(other)
    persistence.record_event(wanted)

    with client.stream("GET", "/events/stream", params={"job_id": str(wanted_job_id)}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    frames = _parse_sse_frames(body)
    assert len(frames) == 1
    assert json.loads(frames[0]["data"])["label"] == "Wanted"


def test_sse_stream_closes_after_wall_clock_cap(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATT_SSE_MAX_SECONDS", "0.2")

    started = time.monotonic()
    with client.stream("GET", "/events/stream") as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    elapsed = time.monotonic() - started

    assert body == ""
    assert elapsed < 2.0


def test_sse_stream_delivers_event_published_to_bus(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATT_SSE_MAX_SECONDS", "5")
    job_id = uuid4()

    def publish_event() -> None:
        time.sleep(0.2)
        asyncio.run(
            event_bus.publish(
                AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Live delivered")
            )
        )

    thread = Thread(target=publish_event)
    thread.start()

    collected_lines: list[str] = []
    with client.stream("GET", "/events/stream", params={"job_id": str(job_id)}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            collected_lines.append(line)
            if collected_lines[-1] == "" and any(entry.startswith("data:") for entry in collected_lines):
                break

    thread.join(timeout=5)
    assert not thread.is_alive()

    frames = _parse_sse_frames("\n".join(collected_lines) + "\n\n")
    assert len(frames) == 1
    assert frames[0]["event"] == EventType.AGENT_STATE
    payload = json.loads(frames[0]["data"])
    assert payload["label"] == "Live delivered"
    assert payload["job_id"] == str(job_id)


def test_sse_stream_ignores_malformed_last_event_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATT_SSE_MAX_SECONDS", "0.3")
    persistence = client.app.state.persistence
    job_id = uuid4()
    created_at = datetime(2026, 7, 18, 1, 0, tzinfo=timezone.utc)
    event = AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Only", created_at=created_at)
    persistence.record_event(event)

    with client.stream("GET", "/events/stream", headers={"Last-Event-ID": "not-a-number"}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    frames = _parse_sse_frames(body)
    assert len(frames) == 1
    assert json.loads(frames[0]["data"])["label"] == "Only"
