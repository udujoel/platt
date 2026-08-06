import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from app import collectors
from app.models import (
    FileInventoryEntry,
    OnboardingRecord,
    TerraformModuleEdge,
    TerraformModuleNode,
)
from app.persistence import Persistence
from app.tools.research import ResearchError

SEED_INFRA_PATH = Path(__file__).resolve().parents[2] / "seed-infra"


@pytest.fixture
def persistence(tmp_path):
    instance = Persistence(db_path=tmp_path / "platt-collectors-test.db")
    try:
        yield instance
    finally:
        instance.close()


class DummyClient:
    """Stands in for an AzdoClient; collectors only check it's not None."""


# -- pipelines ------------------------------------------------------------------------


def test_pipelines_section_is_unavailable_without_a_client(persistence: Persistence) -> None:
    result = asyncio.run(
        collectors.collect_pipelines_section(None, persistence, pipeline_ids=[1])
    )
    assert result.source == "unavailable"
    assert result.runs == []
    assert result.pass_rate is None


def test_pipelines_section_is_unavailable_without_configured_pipeline_ids(persistence: Persistence) -> None:
    result = asyncio.run(
        collectors.collect_pipelines_section(DummyClient(), persistence, pipeline_ids=[])
    )
    assert result.source == "unavailable"


def test_pipelines_section_computes_pass_rate_from_completed_runs(
    persistence: Persistence, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_list_pipeline_runs(client, persistence_arg, *, pipeline_id, **kwargs):
        return {
            "value": [
                {"id": 1, "name": "run-1", "state": "completed", "result": "succeeded", "createdDate": "2024-01-01T00:00:00Z"},
                {"id": 2, "name": "run-2", "state": "completed", "result": "failed", "createdDate": "2024-01-02T00:00:00Z"},
                {"id": 3, "name": "run-3", "state": "inProgress", "result": None, "createdDate": "2024-01-03T00:00:00Z"},
            ]
        }

    monkeypatch.setattr(collectors.azdo_tools, "list_pipeline_runs", fake_list_pipeline_runs)

    result = asyncio.run(
        collectors.collect_pipelines_section(DummyClient(), persistence, pipeline_ids=[42])
    )

    assert result.source == "live"
    assert len(result.runs) == 3
    # 1 of 2 completed runs succeeded
    assert result.pass_rate == 50.0


def test_pipelines_section_bounds_runs_per_pipeline(
    persistence: Persistence, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_list_pipeline_runs(client, persistence_arg, *, pipeline_id, **kwargs):
        return {
            "value": [
                {"id": n, "state": "completed", "result": "succeeded"} for n in range(25)
            ]
        }

    monkeypatch.setattr(collectors.azdo_tools, "list_pipeline_runs", fake_list_pipeline_runs)

    result = asyncio.run(
        collectors.collect_pipelines_section(
            DummyClient(), persistence, pipeline_ids=[1], runs_per_pipeline=5
        )
    )
    assert len(result.runs) == 5


def test_pipelines_section_is_unavailable_when_azdo_call_fails(
    persistence: Persistence, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.clients.azdo import AzdoRequestError

    async def fake_list_pipeline_runs(client, persistence_arg, *, pipeline_id, **kwargs):
        raise AzdoRequestError("GET", "https://example", 500, "boom")

    monkeypatch.setattr(collectors.azdo_tools, "list_pipeline_runs", fake_list_pipeline_runs)

    result = asyncio.run(
        collectors.collect_pipelines_section(DummyClient(), persistence, pipeline_ids=[1])
    )
    assert result.source == "unavailable"
    assert result.runs == []


# -- pull requests --------------------------------------------------------------------


def test_pull_requests_section_is_unavailable_without_a_client(persistence: Persistence) -> None:
    result = asyncio.run(
        collectors.collect_pull_requests_section(None, persistence, repository_id="repo-1")
    )
    assert result.source == "unavailable"
    assert result.pull_requests == []


def test_pull_requests_section_maps_live_results(
    persistence: Persistence, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_list_prs(client, persistence_arg, *, repository_id, **kwargs):
        return {
            "value": [
                {"pullRequestId": 142, "title": "Add storage account", "creationDate": "2024-01-01T00:00:00Z"},
            ]
        }

    monkeypatch.setattr(collectors.azdo_tools, "list_prs", fake_list_prs)

    result = asyncio.run(
        collectors.collect_pull_requests_section(DummyClient(), persistence, repository_id="repo-1")
    )
    assert result.source == "live"
    assert len(result.pull_requests) == 1
    assert result.pull_requests[0].id == 142
    assert result.pull_requests[0].title == "Add storage account"
    assert result.pull_requests[0].age_days >= 0


# -- versions ---------------------------------------------------------------------------


def test_versions_section_reuses_version_bump_constraint_check(persistence: Persistence) -> None:
    async def fetcher(url: str):
        return {"versions": [{"version": "4.0.0"}, {"version": "4.10.2"}]}

    result = asyncio.run(
        collectors.collect_versions_section(persistence, seed_infra_path=SEED_INFRA_PATH, http_fetcher=fetcher)
    )
    assert result.source == "live"
    assert len(result.versions) == 1
    posture = result.versions[0]
    assert posture.name == "azurerm provider"
    assert posture.current == "~> 4.0"
    assert posture.latest == "4.10.2"
    assert posture.bump_needed is False  # ~> 4.0 allows 4.10.2


def test_versions_section_is_unavailable_when_registry_fetch_fails(persistence: Persistence) -> None:
    async def fetcher(url: str):
        raise ResearchError("boom")

    result = asyncio.run(
        collectors.collect_versions_section(persistence, seed_infra_path=SEED_INFRA_PATH, http_fetcher=fetcher)
    )
    assert result.source == "unavailable"
    assert result.versions == []


def test_versions_section_is_unavailable_with_a_bad_seed_infra_path(
    persistence: Persistence, tmp_path: Path
) -> None:
    async def fetcher(url: str):
        raise AssertionError("should not be called")

    result = asyncio.run(
        collectors.collect_versions_section(persistence, seed_infra_path=tmp_path, http_fetcher=fetcher)
    )
    assert result.source == "unavailable"


# -- jobs / approvals ---------------------------------------------------------------------


def test_jobs_section_reflects_persisted_jobs(persistence: Persistence) -> None:
    job_id_a, job_id_b = uuid4(), uuid4()
    persistence.record_job(job_id_a, prompt="a", status="running")
    persistence.record_job(job_id_b, prompt="b", status="succeeded")

    result = collectors.collect_jobs_section(persistence, recent_limit=10)

    assert result.source == "live"
    assert result.counts_by_status == {"running": 1, "succeeded": 1}
    assert len(result.recent) == 2


def test_approvals_pending_section_counts_only_pending(persistence: Persistence) -> None:
    job_id = uuid4()
    persistence.create_approval(uuid4(), job_id, plan_hash="p1", commit_sha="c1", scope="s")
    decided_id = uuid4()
    persistence.create_approval(decided_id, job_id, plan_hash="p2", commit_sha="c2", scope="s")
    persistence.decide_approval(decided_id, approver="alice", status="approved", expires_at=None)

    result = collectors.collect_approvals_pending_section(persistence)

    assert result.source == "live"
    assert result.count == 1


# -- module graph -----------------------------------------------------------------------


def test_module_graph_is_unavailable_without_an_onboarding_record(persistence: Persistence) -> None:
    result = collectors.collect_module_graph(persistence)
    assert result.source == "unavailable"
    assert result.nodes == []
    assert result.edges == []


def test_module_graph_maps_the_most_recent_onboarding_record(persistence: Persistence) -> None:
    from datetime import datetime, timezone

    older = OnboardingRecord(
        id=uuid4(),
        repository_path="/repo-old",
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        files=[FileInventoryEntry(path="a.tf", size_bytes=1)],
        terraform_modules=[],
        pipeline_yamls=[],
    )
    newer = OnboardingRecord(
        id=uuid4(),
        repository_path="/repo-new",
        created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        files=[FileInventoryEntry(path="main.tf", size_bytes=2)],
        terraform_modules=[],
        terraform_module_nodes=[TerraformModuleNode(path="modules/network", variables=["cidr"], outputs=["id"])],
        terraform_module_edges=[
            TerraformModuleEdge(caller_path="main.tf", module_name="network", source="../modules/network", target_path="modules/network")
        ],
        pipeline_yamls=[],
    )
    persistence.save_onboarding_record(older)
    persistence.save_onboarding_record(newer)

    result = collectors.collect_module_graph(persistence)

    assert result.source == "live"
    assert result.onboarding_id == newer.id
    assert result.repository_path == "/repo-new"
    assert len(result.nodes) == 1
    assert result.nodes[0].path == "modules/network"
    assert len(result.edges) == 1
    assert result.edges[0].module_name == "network"


# -- full dashboard combination ----------------------------------------------------------


def test_collect_dashboard_combines_unavailable_sections_gracefully(persistence: Persistence) -> None:
    async def fetcher(url: str):
        raise ResearchError("no network in test")

    payload = asyncio.run(
        collectors.collect_dashboard(
            persistence,
            azdo_client=None,
            repository_id="",
            pipeline_ids=[],
            seed_infra_path=SEED_INFRA_PATH,
            http_fetcher=fetcher,
        )
    )

    assert payload.pipelines.source == "unavailable"
    assert payload.open_pull_requests.source == "unavailable"
    assert payload.versions.source == "unavailable"
    assert payload.jobs.source == "live"
    assert payload.approvals_pending.source == "live"


# -- cache ------------------------------------------------------------------------------


def test_dashboard_cache_returns_none_after_ttl_expires() -> None:
    cache = collectors.DashboardCache(ttl_seconds=10.0)
    payload = collectors.DashboardPayload(
        pipelines=collectors.PipelineSection(),
        open_pull_requests=collectors.PullRequestSection(),
        versions=collectors.VersionSection(),
        jobs=collectors.JobsSection(),
        approvals_pending=collectors.ApprovalsPendingSection(),
    )
    cache.set(payload, now=100.0)

    assert cache.get(now=105.0) is payload
    assert cache.get(now=111.0) is None
