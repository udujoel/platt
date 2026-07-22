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

    response = client.post("/version-bump/trigger")

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["job_id"]
