import json
import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.routers.version_bump import VERSION_BUMP_SCHEDULE_CRON


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "platt-version-bump-router-test.db")) as test_client:
        yield test_client


def test_schedule_reports_the_configured_cadence_and_is_not_wired(client: TestClient) -> None:
    response = client.get("/version-bump/schedule")

    assert response.status_code == 200
    body = response.json()
    assert body["cron"] == VERSION_BUMP_SCHEDULE_CRON
    assert body["wired"] is False


def test_trigger_returns_503_when_azdo_is_not_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZDO_ORG_URL", raising=False)
    monkeypatch.delenv("AZDO_PROJECT", raising=False)
    monkeypatch.delenv("AZDO_PAT", raising=False)

    response = client.post("/version-bump/trigger")

    assert response.status_code == 503
    assert "Azure DevOps is not configured" in response.json()["detail"]


def test_trigger_accepts_the_job_when_azdo_is_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZDO_ORG_URL", "https://dev.azure.com/myorg")
    monkeypatch.setenv("AZDO_PROJECT", "MyProject")
    monkeypatch.setenv("AZDO_PAT", "secret-pat")

    # The background job would otherwise hit the live Terraform Registry via
    # default_http_fetcher before test teardown cancels it; stub it out so
    # this test stays hermetic and only exercises the 202 acceptance path.
    async def _noop_version_bump_check(**kwargs) -> None:
        del kwargs

    monkeypatch.setattr("app.routers.version_bump.run_version_bump_check", _noop_version_bump_check)

    response = client.post("/version-bump/trigger")

    assert response.status_code == 202


def test_trigger_publishes_a_terminal_concerned_state_when_the_background_job_raises(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("AZDO_ORG_URL", "https://dev.azure.com/myorg")
    monkeypatch.setenv("AZDO_PROJECT", "MyProject")
    monkeypatch.setenv("AZDO_PAT", "secret-pat")

    async def _boom(**kwargs) -> None:
        del kwargs
        raise RuntimeError("simulated version-bump failure")

    monkeypatch.setattr("app.routers.version_bump.run_version_bump_check", _boom)

    with caplog.at_level("ERROR"):
        response = client.post("/version-bump/trigger")
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        for _ in range(100):
            if not client.app.state.background_tasks:
                break
            time.sleep(0.02)

    assert "Background task failed" in caplog.text

    events = client.app.state.persistence.list_job_events(UUID(job_id))
    agent_states = [json.loads(event["payload"]) for event in events if event["type"] == "agent_state"]
    assert agent_states, "expected at least one agent_state event to have been recorded"
    assert agent_states[-1]["state"] == "concerned"
    assert agent_states[-1]["label"] == "Version-bump check failed"
