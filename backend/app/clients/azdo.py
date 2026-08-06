"""Thin async client for Azure DevOps REST API v7.1.

Credentials (``AZDO_ORG_URL``, ``AZDO_PROJECT``, ``AZDO_PAT``) are read once from
the environment into :class:`AzdoConfig` and held only in memory for the life of
the client; they are never persisted, logged, or echoed back in any response.

Importing this module never touches the environment or the network, so it is
always safe to import regardless of whether Azure DevOps is configured. Callers
that need a client construct one explicitly via :meth:`AzdoClient.from_environment`,
which raises :class:`AzdoNotConfiguredError` when credentials are missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

API_VERSION = "7.1"


class AzdoError(RuntimeError):
    """Base class for all errors raised by the Azure DevOps client."""


class AzdoNotConfiguredError(AzdoError):
    """Raised when required Azure DevOps environment variables are missing."""


class AzdoRequestError(AzdoError):
    """Raised when a request to Azure DevOps fails.

    Covers both HTTP-level failures (non-2xx responses, ``status_code`` set)
    and transport-level failures (timeouts, connection errors, DNS failures,
    ...) where no response was ever received and ``status_code`` is ``None``.
    Either way this is the one error type tool callers need to catch to
    guarantee an audit entry gets written for a failed call.
    """

    def __init__(self, method: str, url: str, status_code: int | None, detail: str) -> None:
        self.method = method
        self.url = url
        self.status_code = status_code
        self.detail = detail
        if status_code is None:
            message = f"{method} {url} failed: {detail}"
        else:
            message = f"{method} {url} failed with {status_code}: {detail}"
        super().__init__(message)


@dataclass(frozen=True)
class AzdoConfig:
    org_url: str
    project: str
    pat: str

    @classmethod
    def from_environment(cls) -> AzdoConfig:
        org_url = os.environ.get("AZDO_ORG_URL", "").strip()
        project = os.environ.get("AZDO_PROJECT", "").strip()
        pat = os.environ.get("AZDO_PAT", "").strip()
        missing = [
            name
            for name, value in (("AZDO_ORG_URL", org_url), ("AZDO_PROJECT", project), ("AZDO_PAT", pat))
            if not value
        ]
        if missing:
            raise AzdoNotConfiguredError(
                "Azure DevOps is not configured; missing environment variable(s): " + ", ".join(missing)
            )
        return cls(org_url=org_url.rstrip("/"), project=project, pat=pat)


class AzdoClient:
    """Async wrapper over Azure DevOps REST API v7.1, PAT basic auth.

    A PAT authenticates as HTTP Basic auth with an empty username, per Azure
    DevOps convention.
    """

    def __init__(self, config: AzdoConfig, *, timeout: float = 30.0) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=f"{config.org_url}/{config.project}/_apis",
            auth=("", config.pat),
            timeout=timeout,
        )

    @classmethod
    def from_environment(cls, *, timeout: float = 30.0) -> AzdoClient:
        return cls(AzdoConfig.from_environment(), timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AzdoClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        content_type: str = "application/json",
        extra_headers: dict[str, str] | None = None,
        raw_response: bool = False,
    ) -> Any:
        merged_params = {**(params or {}), "api-version": API_VERSION}
        headers = {"Content-Type": content_type}
        if extra_headers:
            headers.update(extra_headers)
        try:
            response = await self._client.request(
                method, url, params=merged_params, json=json_body, headers=headers
            )
        except httpx.HTTPError as exc:
            # Transport-level failures (timeouts, connection errors, ...) never
            # produce a response, so they must be wrapped here rather than left
            # to escape as a bare httpx exception: tool callers only catch
            # AzdoError to guarantee an audit entry for every failed call.
            raise AzdoRequestError(method, url, None, str(exc)) from exc
        if response.status_code >= 400:
            raise AzdoRequestError(method, str(response.url), response.status_code, response.text[:500])
        if raw_response:
            return response
        if not response.content:
            return {}
        return response.json()

    # -- Process template ----------------------------------------------------

    async def get_process_template(self) -> dict[str, Any]:
        """Return the project's capabilities, including its process template name."""
        url = f"{self._config.org_url}/_apis/projects/{self._config.project}"
        return await self._request("GET", url, params={"includeCapabilities": "true"})

    # -- Branches / pushes -----------------------------------------------------

    async def get_branch(self, repository_id: str, branch_name: str) -> dict[str, Any] | None:
        """Return the ``refs/heads/<branch_name>`` ref object, or ``None`` if it doesn't exist yet."""
        url = f"git/repositories/{repository_id}/refs"
        response = await self._request("GET", url, params={"filter": f"heads/{branch_name}"})
        full_name = f"refs/heads/{branch_name}"
        for ref in response.get("value", []):
            if ref.get("name") == full_name:
                return ref
        return None

    async def push_file(
        self,
        repository_id: str,
        *,
        branch_name: str,
        base_object_id: str,
        file_path: str,
        content: str,
        change_type: str,
        comment: str,
    ) -> dict[str, Any]:
        """Push one commit adding/editing a single file, fast-forwarding from ``base_object_id``.

        ``base_object_id`` is the branch's current tip when pushing a follow-up
        commit, or the base branch's tip when this push creates ``branch_name``
        for the first time (Azure DevOps derives the new branch's parent from
        the ref update's ``oldObjectId`` in that case).
        """
        url = f"git/repositories/{repository_id}/pushes"
        body = {
            "refUpdates": [{"name": f"refs/heads/{branch_name}", "oldObjectId": base_object_id}],
            "commits": [
                {
                    "comment": comment,
                    "changes": [
                        {
                            "changeType": change_type,
                            "item": {"path": f"/{file_path.lstrip('/')}"},
                            "newContent": {"content": content, "contentType": "rawtext"},
                        }
                    ],
                }
            ],
        }
        return await self._request("POST", url, json_body=body)

    # -- Pull requests --------------------------------------------------------

    async def create_pull_request(
        self,
        repository_id: str,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str = "",
    ) -> dict[str, Any]:
        url = f"git/repositories/{repository_id}/pullrequests"
        body = {
            "sourceRefName": source_branch,
            "targetRefName": target_branch,
            "title": title,
            "description": description,
        }
        return await self._request("POST", url, json_body=body)

    async def get_pull_request(self, repository_id: str, pull_request_id: int) -> dict[str, Any]:
        url = f"git/repositories/{repository_id}/pullrequests/{pull_request_id}"
        return await self._request("GET", url)

    async def list_pull_requests(
        self, repository_id: str, *, status: str = "active", top: int = 20
    ) -> dict[str, Any]:
        url = f"git/repositories/{repository_id}/pullrequests"
        return await self._request(
            "GET", url, params={"searchCriteria.status": status, "$top": top}
        )

    async def comment_pull_request(
        self, repository_id: str, pull_request_id: int, *, comment: str
    ) -> dict[str, Any]:
        url = f"git/repositories/{repository_id}/pullrequests/{pull_request_id}/threads"
        body = {"comments": [{"parentCommentId": 0, "content": comment, "commentType": 1}], "status": 1}
        return await self._request("POST", url, json_body=body)

    # -- Pipelines --------------------------------------------------------------

    async def run_pipeline(
        self, pipeline_id: int, *, branch: str | None = None, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"pipelines/{pipeline_id}/runs"
        body: dict[str, Any] = {}
        if branch:
            body["resources"] = {"repositories": {"self": {"refName": branch}}}
        if variables:
            body["variables"] = variables
        return await self._request("POST", url, json_body=body)

    async def get_pipeline_run(self, pipeline_id: int, run_id: int) -> dict[str, Any]:
        url = f"pipelines/{pipeline_id}/runs/{run_id}"
        return await self._request("GET", url)

    async def list_pipeline_runs(self, pipeline_id: int) -> dict[str, Any]:
        url = f"pipelines/{pipeline_id}/runs"
        return await self._request("GET", url)

    async def list_pipeline_logs(self, pipeline_id: int, run_id: int) -> dict[str, Any]:
        url = f"pipelines/{pipeline_id}/runs/{run_id}/logs"
        return await self._request("GET", url)

    async def get_pipeline_log_content(self, pipeline_id: int, run_id: int, log_id: int) -> str:
        """Fetch one log's raw text.

        The Get Log endpoint returns a JSON envelope (``{"lineCount": ..., "value":
        [...]}``) by default; sending ``Accept: text/plain`` instead makes it
        return the log body as plain text, which is what callers of this method
        want. ``Content-Type`` is irrelevant here since a GET has no request body.
        """
        url = f"pipelines/{pipeline_id}/runs/{run_id}/logs/{log_id}"
        response = await self._request(
            "GET", url, extra_headers={"Accept": "text/plain"}, raw_response=True
        )
        return response.text

    # -- Work items ---------------------------------------------------------

    async def create_work_item(
        self, work_item_type: str, *, title: str, fields: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"wit/workitems/${work_item_type}"
        operations = [{"op": "add", "path": "/fields/System.Title", "value": title}]
        for field_name, value in (fields or {}).items():
            operations.append({"op": "add", "path": f"/fields/{field_name}", "value": value})
        return await self._request(
            "POST", url, json_body=operations, content_type="application/json-patch+json"
        )

    async def update_work_item_state(self, work_item_id: int, *, state: str) -> dict[str, Any]:
        url = f"wit/workitems/{work_item_id}"
        operations = [{"op": "add", "path": "/fields/System.State", "value": state}]
        return await self._request(
            "PATCH", url, json_body=operations, content_type="application/json-patch+json"
        )

    async def list_work_items(self, wiql_query: str) -> dict[str, Any]:
        url = "wit/wiql"
        return await self._request("POST", url, json_body={"query": wiql_query})

    # -- Wiki -----------------------------------------------------------------

    async def get_wiki_page(self, wiki_identifier: str, path: str) -> dict[str, Any]:
        url = f"wiki/wikis/{wiki_identifier}/pages"
        response = await self._request(
            "GET", url, params={"path": path, "includeContent": "true"}, raw_response=True
        )
        payload = response.json() if response.content else {}
        payload["eTag"] = response.headers.get("ETag")
        return payload

    async def update_wiki_page(
        self, wiki_identifier: str, path: str, *, content: str, version: str | None = None
    ) -> dict[str, Any]:
        url = f"wiki/wikis/{wiki_identifier}/pages"
        extra_headers = {"If-Match": version} if version else None
        return await self._request(
            "PUT",
            url,
            params={"path": path},
            json_body={"content": content},
            extra_headers=extra_headers,
        )
