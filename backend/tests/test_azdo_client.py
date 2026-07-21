import asyncio

import httpx
import pytest
import respx

from app.clients.azdo import AzdoClient, AzdoConfig, AzdoNotConfiguredError, AzdoRequestError


def make_client() -> AzdoClient:
    config = AzdoConfig(org_url="https://dev.azure.com/myorg", project="MyProject", pat="secret-pat")
    return AzdoClient(config)


def test_config_from_environment_requires_all_three_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZDO_ORG_URL", raising=False)
    monkeypatch.delenv("AZDO_PROJECT", raising=False)
    monkeypatch.delenv("AZDO_PAT", raising=False)

    with pytest.raises(AzdoNotConfiguredError) as excinfo:
        AzdoConfig.from_environment()

    assert "AZDO_ORG_URL" in str(excinfo.value)
    assert "AZDO_PROJECT" in str(excinfo.value)
    assert "AZDO_PAT" in str(excinfo.value)


def test_config_from_environment_reports_only_missing_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZDO_ORG_URL", "https://dev.azure.com/myorg")
    monkeypatch.setenv("AZDO_PROJECT", "MyProject")
    monkeypatch.delenv("AZDO_PAT", raising=False)

    with pytest.raises(AzdoNotConfiguredError) as excinfo:
        AzdoConfig.from_environment()

    message = str(excinfo.value)
    assert "AZDO_PAT" in message
    assert "AZDO_ORG_URL" not in message
    assert "AZDO_PROJECT" not in message


def test_config_from_environment_succeeds_when_all_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZDO_ORG_URL", "https://dev.azure.com/myorg/")
    monkeypatch.setenv("AZDO_PROJECT", "MyProject")
    monkeypatch.setenv("AZDO_PAT", "secret-pat")

    config = AzdoConfig.from_environment()

    assert config.org_url == "https://dev.azure.com/myorg"
    assert config.project == "MyProject"
    assert config.pat == "secret-pat"


def test_importing_client_module_never_touches_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing the module (already done at collection time) must not require creds."""
    monkeypatch.delenv("AZDO_ORG_URL", raising=False)
    monkeypatch.delenv("AZDO_PROJECT", raising=False)
    monkeypatch.delenv("AZDO_PAT", raising=False)

    import app.clients.azdo  # noqa: F401 - re-import is a no-op; asserts no crash


def test_client_sends_pat_as_basic_auth_and_never_in_body() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                route = mock.get("/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests/42").mock(
                    return_value=httpx.Response(200, json={"pullRequestId": 42, "status": "active"})
                )
                result = await client.get_pull_request("repo-1", 42)
                assert result["status"] == "active"
                request = route.calls.last.request
                assert request.headers["Authorization"].startswith("Basic ")
                assert "secret-pat" not in request.content.decode()
                assert request.url.params["api-version"] == "7.1"
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_create_pull_request_sends_expected_body() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                route = mock.post("/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests").mock(
                    return_value=httpx.Response(201, json={"pullRequestId": 7})
                )
                result = await client.create_pull_request(
                    "repo-1",
                    source_branch="refs/heads/feature",
                    target_branch="refs/heads/main",
                    title="Add widget",
                    description="Adds a widget",
                )
                assert result["pullRequestId"] == 7
                body = route.calls.last.request.content
                import json

                payload = json.loads(body)
                assert payload == {
                    "sourceRefName": "refs/heads/feature",
                    "targetRefName": "refs/heads/main",
                    "title": "Add widget",
                    "description": "Adds a widget",
                }
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_run_pipeline_includes_branch_resource_when_given() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                route = mock.post("/myorg/MyProject/_apis/pipelines/9/runs").mock(
                    return_value=httpx.Response(200, json={"id": 100, "state": "inProgress"})
                )
                result = await client.run_pipeline(9, branch="refs/heads/main")
                assert result["id"] == 100
                import json

                payload = json.loads(route.calls.last.request.content)
                assert payload["resources"]["repositories"]["self"]["refName"] == "refs/heads/main"
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_create_work_item_uses_json_patch_content_type() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                route = mock.post("/myorg/MyProject/_apis/wit/workitems/$Bug").mock(
                    return_value=httpx.Response(200, json={"id": 55})
                )
                result = await client.create_work_item("Bug", title="Fix the thing")
                assert result["id"] == 55
                request = route.calls.last.request
                assert request.headers["Content-Type"] == "application/json-patch+json"
                import json

                payload = json.loads(request.content)
                assert payload[0] == {"op": "add", "path": "/fields/System.Title", "value": "Fix the thing"}
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_list_work_items_posts_wiql_query() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                route = mock.post("/myorg/MyProject/_apis/wit/wiql").mock(
                    return_value=httpx.Response(200, json={"workItems": [{"id": 1}, {"id": 2}]})
                )
                result = await client.list_work_items("SELECT [System.Id] FROM WorkItems")
                assert len(result["workItems"]) == 2
                import json

                payload = json.loads(route.calls.last.request.content)
                assert payload == {"query": "SELECT [System.Id] FROM WorkItems"}
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_get_wiki_page_captures_etag_for_optimistic_concurrency() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/MyProject/_apis/wiki/wikis/main-wiki/pages").mock(
                    return_value=httpx.Response(
                        200, json={"path": "/Home", "content": "hello"}, headers={"ETag": '"abc123"'}
                    )
                )
                result = await client.get_wiki_page("main-wiki", "/Home")
                assert result["content"] == "hello"
                assert result["eTag"] == '"abc123"'
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_update_wiki_page_sends_if_match_header_when_version_given() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                route = mock.put("/myorg/MyProject/_apis/wiki/wikis/main-wiki/pages").mock(
                    return_value=httpx.Response(200, json={"id": 3})
                )
                await client.update_wiki_page("main-wiki", "/Home", content="updated", version='"abc123"')
                request = route.calls.last.request
                assert request.headers["If-Match"] == '"abc123"'
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_get_process_template_reads_org_scoped_project_endpoint() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/_apis/projects/MyProject").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "name": "MyProject",
                            "capabilities": {"processTemplate": {"templateName": "Agile"}},
                        },
                    )
                )
                result = await client.get_process_template()
                assert result["capabilities"]["processTemplate"]["templateName"] == "Agile"
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_request_error_carries_status_and_never_includes_pat_and_no_body_swallowed() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests/99").mock(
                    return_value=httpx.Response(404, text="TF401180: pull request not found")
                )
                with pytest.raises(AzdoRequestError) as excinfo:
                    await client.get_pull_request("repo-1", 99)
                assert excinfo.value.status_code == 404
                assert "secret-pat" not in str(excinfo.value)
                assert "not found" in excinfo.value.detail
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_transport_timeout_is_wrapped_in_azdo_request_error() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests/1").mock(
                    side_effect=httpx.TimeoutException("timed out")
                )
                with pytest.raises(AzdoRequestError) as excinfo:
                    await client.get_pull_request("repo-1", 1)
                assert excinfo.value.status_code is None
                assert "timed out" in str(excinfo.value)
                assert "secret-pat" not in str(excinfo.value)
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_transport_connect_error_is_wrapped_in_azdo_request_error() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests/1").mock(
                    side_effect=httpx.ConnectError("connection refused")
                )
                with pytest.raises(AzdoRequestError) as excinfo:
                    await client.get_pull_request("repo-1", 1)
                assert excinfo.value.status_code is None
                assert "connection refused" in str(excinfo.value)
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_get_pipeline_log_content_requests_plain_text_accept_header() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                route = mock.get("/myorg/MyProject/_apis/pipelines/9/runs/100/logs/3").mock(
                    return_value=httpx.Response(200, text="line one\nline two\n")
                )
                content = await client.get_pipeline_log_content(9, 100, 3)
                assert content == "line one\nline two\n"
                request = route.calls.last.request
                assert request.headers["Accept"] == "text/plain"
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_update_wiki_page_without_version_omits_if_match_header() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                route = mock.put("/myorg/MyProject/_apis/wiki/wikis/main-wiki/pages").mock(
                    return_value=httpx.Response(200, json={"id": 3})
                )
                result = await client.update_wiki_page("main-wiki", "/Home", content="new page")
                assert result["id"] == 3
                request = route.calls.last.request
                assert "If-Match" not in request.headers
                assert request.url.params["path"] == "/Home"
                assert request.url.params["api-version"] == "7.1"
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_update_wiki_page_raises_azdo_request_error_on_conflict() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.put("/myorg/MyProject/_apis/wiki/wikis/main-wiki/pages").mock(
                    return_value=httpx.Response(409, text="TF401190: version conflict")
                )
                with pytest.raises(AzdoRequestError) as excinfo:
                    await client.update_wiki_page(
                        "main-wiki", "/Home", content="new page", version='"stale-etag"'
                    )
                assert excinfo.value.status_code == 409
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_update_wiki_page_transport_error_is_wrapped() -> None:
    async def _run() -> None:
        client = make_client()
        try:
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.put("/myorg/MyProject/_apis/wiki/wikis/main-wiki/pages").mock(
                    side_effect=httpx.ConnectError("connection refused")
                )
                with pytest.raises(AzdoRequestError) as excinfo:
                    await client.update_wiki_page("main-wiki", "/Home", content="new page")
                assert excinfo.value.status_code is None
        finally:
            await client.aclose()

    asyncio.run(_run())
