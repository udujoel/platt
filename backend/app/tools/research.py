"""Audited Terraform Registry / release-notes research tool (PRD §F4).

Fetches the latest published version for a Terraform provider from the
public Terraform Registry API, and best-effort release notes from GitHub, so
the version-bump job can decide whether a bump is warranted. The HTTP fetch
itself is injected (``HttpFetcher``) so callers -- and tests -- never need
real network access. Every fetch still writes exactly one audit entry,
mirroring :mod:`app.tools.azdo`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

import httpx

from app.event_bus import EventBus
from app.models import AuditEntryEvent
from app.persistence import Persistence

TOOL_NAME = "research"
TERRAFORM_REGISTRY_BASE_URL = "https://registry.terraform.io"
GITHUB_API_BASE_URL = "https://api.github.com"
_MAX_VALUE_CHARS = 200

# Fetches ``url`` and returns its parsed JSON body. Injectable so tests never
# need real network access; ``default_http_fetcher`` is the only
# implementation that actually touches the network.
HttpFetcher = Callable[[str], Awaitable[dict[str, Any]]]


class ResearchError(RuntimeError):
    """Raised when a registry fetch fails or returns an unexpected shape."""


async def default_http_fetcher(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()


@dataclass(frozen=True)
class ProviderVersionInfo:
    namespace: str
    name: str
    latest_version: str


def _version_sort_key(version: str) -> tuple[int, ...]:
    """Best-effort numeric sort key: non-numeric/pre-release versions sort lowest."""
    core = version.split("-", 1)[0].split("+", 1)[0]
    try:
        return tuple(int(part) for part in core.split("."))
    except ValueError:
        return (0,)


async def _audit(
    persistence: Persistence,
    event_bus: EventBus | None,
    job_id: UUID | None,
    action: str,
    *,
    request_summary: str,
    ok: bool,
    result_summary: str,
) -> None:
    status = "succeeded" if ok else "error"
    outcome = f"{status} | request: {request_summary} | result: {result_summary}"
    persistence.record_audit_entry(job_id, tool=TOOL_NAME, action=action, outcome=outcome)
    if event_bus is not None and job_id is not None:
        await event_bus.publish(
            AuditEntryEvent(job_id=job_id, tool=TOOL_NAME, action=action, outcome=status, summary=outcome[:512])
        )


async def fetch_latest_provider_version(
    fetcher: HttpFetcher,
    persistence: Persistence,
    *,
    namespace: str = "hashicorp",
    name: str = "azurerm",
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> ProviderVersionInfo:
    """Return the highest published version for a Terraform Registry provider."""
    url = f"{TERRAFORM_REGISTRY_BASE_URL}/v1/providers/{namespace}/{name}/versions"
    request_summary = f"namespace={namespace}, name={name}"

    try:
        data = await fetcher(url)
    except Exception as error:
        await _audit(
            persistence,
            event_bus,
            job_id,
            "fetch_latest_provider_version",
            request_summary=request_summary,
            ok=False,
            result_summary=str(error)[:_MAX_VALUE_CHARS],
        )
        raise ResearchError(f"failed to fetch provider versions for {namespace}/{name}: {error}") from error

    versions = [str(entry["version"]) for entry in (data.get("versions") or []) if entry.get("version")]
    if not versions:
        await _audit(
            persistence,
            event_bus,
            job_id,
            "fetch_latest_provider_version",
            request_summary=request_summary,
            ok=False,
            result_summary="registry returned no versions",
        )
        raise ResearchError(f"Terraform Registry returned no versions for {namespace}/{name}")

    latest = max(versions, key=_version_sort_key)
    await _audit(
        persistence,
        event_bus,
        job_id,
        "fetch_latest_provider_version",
        request_summary=request_summary,
        ok=True,
        result_summary=f"latest={latest}",
    )
    return ProviderVersionInfo(namespace=namespace, name=name, latest_version=latest)


async def fetch_provider_release_notes(
    fetcher: HttpFetcher,
    persistence: Persistence,
    *,
    org: str = "hashicorp",
    repo: str = "terraform-provider-azurerm",
    version: str,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> str:
    """Best-effort release notes body for ``version`` from GitHub releases.

    A missing/unreachable release is not fatal to the version-bump job (the
    significance assessment still proceeds, just without notes to read), so
    this returns an empty string on failure instead of raising.
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/releases/tags/v{version}"
    request_summary = f"org={org}, repo={repo}, version={version}"

    try:
        data = await fetcher(url)
    except Exception as error:
        await _audit(
            persistence,
            event_bus,
            job_id,
            "fetch_provider_release_notes",
            request_summary=request_summary,
            ok=False,
            result_summary=str(error)[:_MAX_VALUE_CHARS],
        )
        return ""

    body = str(data.get("body") or "")
    await _audit(
        persistence,
        event_bus,
        job_id,
        "fetch_provider_release_notes",
        request_summary=request_summary,
        ok=True,
        result_summary=f"chars={len(body)}",
    )
    return body
