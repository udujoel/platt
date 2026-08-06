import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "platt-dashboard-router-test.db")) as test_client:
        yield test_client


def test_dashboard_is_all_unavailable_when_azdo_is_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AZDO_ORG_URL", raising=False)
    monkeypatch.delenv("AZDO_PROJECT", raising=False)
    monkeypatch.delenv("AZDO_PAT", raising=False)

    response = client.get("/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["pipelines"]["source"] == "unavailable"
    assert body["pipelines"]["runs"] == []
    assert body["open_pull_requests"]["source"] == "unavailable"
    assert body["open_pull_requests"]["pull_requests"] == []
    # jobs/approvals are local-persistence backed, always live even without AzDO
    assert body["jobs"]["source"] == "live"
    assert body["approvals_pending"]["source"] == "live"


def test_dashboard_response_is_cached_within_the_ttl(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AZDO_ORG_URL", raising=False)
    monkeypatch.delenv("AZDO_PROJECT", raising=False)
    monkeypatch.delenv("AZDO_PAT", raising=False)

    calls = []

    async def fake_collect_dashboard(*args, **kwargs):
        calls.append(1)
        from app.collectors import (
            ApprovalsPendingSection,
            DashboardPayload,
            JobsSection,
            PipelineSection,
            PullRequestSection,
            VersionSection,
        )

        return DashboardPayload(
            pipelines=PipelineSection(),
            open_pull_requests=PullRequestSection(),
            versions=VersionSection(),
            jobs=JobsSection(),
            approvals_pending=ApprovalsPendingSection(),
        )

    monkeypatch.setattr("app.routers.dashboard.collect_dashboard", fake_collect_dashboard)

    first = client.get("/dashboard")
    second = client.get("/dashboard")

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 1


def test_module_graph_is_unavailable_without_any_onboarding_record(client: TestClient) -> None:
    response = client.get("/dashboard/module-graph")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "unavailable"
    assert body["nodes"] == []
    assert body["edges"] == []


def test_module_graph_maps_a_persisted_onboarding_record(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLATT_ONBOARDING_ROOT", str(tmp_path))
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "main.tf").write_text(
        '''module "network" {
  source = "../../modules/network"
}
'''
    )

    onboard_response = client.post("/onboarding", json={"repository_path": str(repository)})
    assert onboard_response.status_code == 201

    response = client.get("/dashboard/module-graph")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "live"
    assert body["repository_path"] == str(repository)
