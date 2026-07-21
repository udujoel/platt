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
    """Raised when Azure DevOps responds with a non-2xx status."""

    def __init__(self, method: str, url: str, status_code: int, detail: str) -> None:
        self.method = method
        self.url = url
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{method} {url} failed with {status_code}: {detail}")


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
        raw_response: bool = False,
    ) -> Any:
        merged_params = {**(params or {}), "api-version": API_VERSION}
        headers = {"Content-Type": content_type}
        response = await self._client.request(
            method, url, params=merged_params, json=json_body, headers=headers
        )
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
        url = f"pipelines/{pipeline_id}/runs/{run_id}/logs/{log_id}"
        response = await self._request("GET", url, content_type="text/plain", raw_response=True)
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
        merged_params = {"path": path, "api-version": API_VERSION}
        headers = {"Content-Type": "application/json"}
        if version:
            headers["If-Match"] = version
        response = await self._client.request(
            "PUT", url, params=merged_params, json={"content": content}, headers=headers
        )
        if response.status_code >= 400:
            raise AzdoRequestError("PUT", str(response.url), response.status_code, response.text[:500])
        return response.json() if response.content else {}
