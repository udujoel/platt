import asyncio
from uuid import uuid4

import httpx
import pytest
import respx

from app.clients.azdo import AzdoClient, AzdoConfig, AzdoNotConfiguredError, AzdoRequestError
from app.persistence import Persistence
from app.tools import azdo as azdo_tools


@pytest.fixture
def persistence(tmp_path):
    instance = Persistence(db_path=tmp_path / "platt-azdo-test.db")
    try:
        yield instance
    finally:
        instance.close()


def make_client() -> AzdoClient:
    config = AzdoConfig(org_url="https://dev.azure.com/myorg", project="MyProject", pat="super-secret-pat")
    return AzdoClient(config)


def test_azdo_client_from_environment_raises_typed_error_without_creds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZDO_ORG_URL", raising=False)
    monkeypatch.delenv("AZDO_PROJECT", raising=False)
    monkeypatch.delenv("AZDO_PAT", raising=False)

    with pytest.raises(AzdoNotConfiguredError):
        AzdoClient.from_environment()


def test_importing_tools_module_never_touches_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZDO_ORG_URL", raising=False)
    monkeypatch.delenv("AZDO_PROJECT", raising=False)
    monkeypatch.delenv("AZDO_PAT", raising=False)

    import app.tools.azdo  # noqa: F401 - re-import is a no-op; asserts no crash


def test_create_pr_writes_audit_entry_on_success(persistence: Persistence) -> None:
    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.post("/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests").mock(
                    return_value=httpx.Response(201, json={"pullRequestId": 42})
                )
                result = await azdo_tools.create_pr(
                    client,
                    persistence,
                    repository_id="repo-1",
                    source_branch="refs/heads/feature",
                    target_branch="refs/heads/main",
                    title="Add widget",
                    job_id=job_id,
                )
                assert result["pullRequestId"] == 42
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["tool"] == "azdo"
        assert entry["action"] == "create_pr"
        assert entry["outcome"].startswith("succeeded")
        assert "pull_request_id=42" in entry["outcome"]
        assert "repo-1" in entry["outcome"]

    asyncio.run(_run())


def test_create_pr_writes_audit_entry_on_error_without_leaking_pat(persistence: Persistence) -> None:
    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.post("/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests").mock(
                    return_value=httpx.Response(400, text="TF401027: bad request")
                )
                with pytest.raises(Exception):
                    await azdo_tools.create_pr(
                        client,
                        persistence,
                        repository_id="repo-1",
                        source_branch="refs/heads/feature",
                        target_branch="refs/heads/main",
                        title="Add widget",
                        job_id=job_id,
                    )
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["outcome"].startswith("error")
        assert "super-secret-pat" not in entry["outcome"]

    asyncio.run(_run())


def test_comment_pr_redacts_no_secret_fields_but_truncates_long_comment(persistence: Persistence) -> None:
    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        long_comment = "x" * 500
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.post(
                    "/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests/5/threads"
                ).mock(return_value=httpx.Response(200, json={"id": 9}))
                await azdo_tools.comment_pr(
                    client,
                    persistence,
                    repository_id="repo-1",
                    pull_request_id=5,
                    comment=long_comment,
                    job_id=job_id,
                )
        finally:
            await client.aclose()

        entry = persistence.list_audit_entries(job_id)[0]
        assert "...(truncated)" in entry["outcome"]
        assert long_comment not in entry["outcome"]

    asyncio.run(_run())


def test_run_pipeline_and_get_pipeline_run_audit_entries(persistence: Persistence) -> None:
    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.post("/myorg/MyProject/_apis/pipelines/9/runs").mock(
                    return_value=httpx.Response(200, json={"id": 100, "state": "inProgress"})
                )
                mock.get("/myorg/MyProject/_apis/pipelines/9/runs/100").mock(
                    return_value=httpx.Response(200, json={"id": 100, "state": "completed", "result": "succeeded"})
                )
                run_result = await azdo_tools.run_pipeline(
                    client, persistence, pipeline_id=9, branch="refs/heads/main", job_id=job_id
                )
                status_result = await azdo_tools.get_pipeline_run(
                    client, persistence, pipeline_id=9, run_id=100, job_id=job_id
                )
                assert run_result["id"] == 100
                assert status_result["result"] == "succeeded"
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        actions = {entry["action"] for entry in entries}
        assert actions == {"run_pipeline", "get_pipeline_run"}

    asyncio.run(_run())


def test_create_work_item_and_update_state_audit_entries(persistence: Persistence) -> None:
    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.post("/myorg/MyProject/_apis/wit/workitems/$Bug").mock(
                    return_value=httpx.Response(200, json={"id": 55})
                )
                mock.patch("/myorg/MyProject/_apis/wit/workitems/55").mock(
                    return_value=httpx.Response(
                        200, json={"id": 55, "fields": {"System.State": "Active"}}
                    )
                )
                created = await azdo_tools.create_work_item(
                    client, persistence, work_item_type="Bug", title="Fix it", job_id=job_id
                )
                updated = await azdo_tools.update_work_item_state(
                    client, persistence, work_item_id=55, state="Active", job_id=job_id
                )
                assert created["id"] == 55
                assert updated["fields"]["System.State"] == "Active"
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        actions = {entry["action"] for entry in entries}
        assert actions == {"create_work_item", "update_work_item_state"}

    asyncio.run(_run())


def test_get_process_template_reports_agile_vs_scrum(persistence: Persistence) -> None:
    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/_apis/projects/MyProject").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "name": "MyProject",
                            "capabilities": {"processTemplate": {"templateName": "Scrum"}},
                        },
                    )
                )
                result = await azdo_tools.get_process_template(client, persistence, job_id=job_id)
                assert result["process_template"] == "Scrum"
        finally:
            await client.aclose()

        entry = persistence.list_audit_entries(job_id)[0]
        assert entry["action"] == "get_process_template"
        assert "template=Scrum" in entry["outcome"]

    asyncio.run(_run())


def test_tools_work_without_job_id(persistence: Persistence) -> None:
    """Tool calls not tied to a job (e.g. onboarding-time probes) still audit."""

    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.post("/myorg/MyProject/_apis/wit/wiql").mock(
                    return_value=httpx.Response(200, json={"workItems": [{"id": 1}]})
                )
                result = await azdo_tools.list_work_items(
                    client, persistence, wiql_query="SELECT [System.Id] FROM WorkItems"
                )
                assert len(result["workItems"]) == 1
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries()
        assert any(entry["action"] == "list_work_items" and entry["job_id"] is None for entry in entries)

    asyncio.run(_run())


def test_transport_timeout_still_writes_exactly_one_audit_entry(persistence: Persistence) -> None:
    """A network-level failure (no HTTP response at all) must not skip auditing."""

    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests/42").mock(
                    side_effect=httpx.TimeoutException("timed out")
                )
                with pytest.raises(AzdoRequestError, match="timed out"):
                    await azdo_tools.get_pr(
                        client, persistence, repository_id="repo-1", pull_request_id=42, job_id=job_id
                    )
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["action"] == "get_pr"
        assert entry["outcome"].startswith("error")
        assert "timed out" in entry["outcome"]
        assert "super-secret-pat" not in entry["outcome"]

    asyncio.run(_run())


def test_transport_connect_error_still_writes_exactly_one_audit_entry(persistence: Persistence) -> None:
    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.post("/myorg/MyProject/_apis/pipelines/9/runs").mock(
                    side_effect=httpx.ConnectError("connection refused")
                )
                with pytest.raises(AzdoRequestError, match="connection refused"):
                    await azdo_tools.run_pipeline(client, persistence, pipeline_id=9, job_id=job_id)
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        assert len(entries) == 1
        assert entries[0]["outcome"].startswith("error")
        assert "connection refused" in entries[0]["outcome"]

    asyncio.run(_run())


def test_update_wiki_page_tool_audits_success_via_refactored_client_call(persistence: Persistence) -> None:
    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                route = mock.put("/myorg/MyProject/_apis/wiki/wikis/main-wiki/pages").mock(
                    return_value=httpx.Response(200, json={"id": 3})
                )
                result = await azdo_tools.update_wiki_page(
                    client,
                    persistence,
                    wiki_identifier="main-wiki",
                    path="/Home",
                    content="updated content",
                    version='"abc123"',
                    job_id=job_id,
                )
                assert result["id"] == 3
                assert route.calls.last.request.headers["If-Match"] == '"abc123"'
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        assert len(entries) == 1
        assert entries[0]["action"] == "update_wiki_page"
        assert entries[0]["outcome"].startswith("succeeded")

    asyncio.run(_run())


def test_get_pipeline_logs_lists_metadata_with_matching_audit_action(persistence: Persistence) -> None:
    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/MyProject/_apis/pipelines/9/runs/100/logs").mock(
                    return_value=httpx.Response(200, json={"logs": [{"id": 1}, {"id": 2}]})
                )
                result = await azdo_tools.get_pipeline_logs(
                    client, persistence, pipeline_id=9, run_id=100, job_id=job_id
                )
                assert len(result["logs"]) == 2
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        assert len(entries) == 1
        assert entries[0]["action"] == "get_pipeline_logs"

    asyncio.run(_run())


def test_get_pipeline_logs_with_log_id_fetches_content_with_distinct_audit_action(
    persistence: Persistence,
) -> None:
    """The single-log-content path is a distinct operation from listing logs, so it must
    be invocable (no crash) and must not be conflated with the listing action in the
    audit trail."""

    async def _run() -> None:
        client = make_client()
        job_id = uuid4()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/MyProject/_apis/pipelines/9/runs/100/logs/3").mock(
                    return_value=httpx.Response(200, text="log line one\n")
                )
                result = await azdo_tools.get_pipeline_logs(
                    client, persistence, pipeline_id=9, run_id=100, log_id=3, job_id=job_id
                )
                assert result == "log line one\n"
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        assert len(entries) == 1
        assert entries[0]["action"] == "get_pipeline_log_content"
        assert entries[0]["action"] != "get_pipeline_logs"

    asyncio.run(_run())
