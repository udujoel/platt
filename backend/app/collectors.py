"""Dashboard data collectors (PRD §F6).

Gathers the real-data sections the dashboard UI renders -- pipeline runs,
open pull requests, provider version posture, persisted job activity, and
pending approvals -- from the same audited AzDO tool layer and persistence
store the rest of the backend uses. Nothing here invents numbers: any
section backed by an unconfigured or unreachable external source comes back
with ``source="unavailable"`` and empty data rather than raising or
guessing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.clients.azdo import AzdoClient, AzdoError
from app.persistence import Persistence
from app.tools import azdo as azdo_tools
from app.tools.research import HttpFetcher, ResearchError, default_http_fetcher, fetch_latest_provider_version
from app.version_bump import VersionBumpError, azurerm_constraint_satisfies, get_current_azurerm_constraint

Source = Literal["live", "unavailable"]

DEFAULT_PIPELINE_RUNS_PER_PIPELINE = 10
DEFAULT_PULL_REQUEST_LIMIT = 10
DEFAULT_RECENT_JOBS_LIMIT = 10


# -- response shapes ----------------------------------------------------------------


class PipelineRunSummary(BaseModel):
    id: int
    name: str | None = None
    state: str | None = None
    result: str | None = None
    created_date: str | None = None


class PipelineSection(BaseModel):
    source: Source = "unavailable"
    runs: list[PipelineRunSummary] = Field(default_factory=list)
    pass_rate: float | None = None


class OpenPullRequestSummary(BaseModel):
    id: int
    title: str
    age_days: int


class PullRequestSection(BaseModel):
    source: Source = "unavailable"
    pull_requests: list[OpenPullRequestSummary] = Field(default_factory=list)


class VersionPosture(BaseModel):
    name: str
    current: str
    latest: str
    bump_needed: bool


class VersionSection(BaseModel):
    source: Source = "unavailable"
    versions: list[VersionPosture] = Field(default_factory=list)


class JobSummary(BaseModel):
    id: str
    prompt: str
    status: str
    created_at: str
    updated_at: str


class JobsSection(BaseModel):
    source: Source = "live"
    counts_by_status: dict[str, int] = Field(default_factory=dict)
    recent: list[JobSummary] = Field(default_factory=list)


class ApprovalsPendingSection(BaseModel):
    source: Source = "live"
    count: int = 0


class DashboardPayload(BaseModel):
    pipelines: PipelineSection
    open_pull_requests: PullRequestSection
    versions: VersionSection
    jobs: JobsSection
    approvals_pending: ApprovalsPendingSection


class ModuleGraphNode(BaseModel):
    path: str
    variables: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class ModuleGraphEdge(BaseModel):
    caller_path: str
    module_name: str
    source: str
    target_path: str


class ModuleGraphPayload(BaseModel):
    source: Source = "unavailable"
    onboarding_id: UUID | None = None
    repository_path: str | None = None
    nodes: list[ModuleGraphNode] = Field(default_factory=list)
    edges: list[ModuleGraphEdge] = Field(default_factory=list)


# -- section collectors --------------------------------------------------------------


async def collect_pipelines_section(
    azdo_client: AzdoClient | None,
    persistence: Persistence,
    *,
    pipeline_ids: list[int],
    runs_per_pipeline: int = DEFAULT_PIPELINE_RUNS_PER_PIPELINE,
) -> PipelineSection:
    """Recent runs and a pass-rate across the configured pipelines, bounded per pipeline."""
    if azdo_client is None or not pipeline_ids:
        return PipelineSection()

    runs: list[PipelineRunSummary] = []
    completed = 0
    succeeded = 0
    try:
        for pipeline_id in pipeline_ids:
            result = await azdo_tools.list_pipeline_runs(azdo_client, persistence, pipeline_id=pipeline_id)
            for run in result.get("value", [])[:runs_per_pipeline]:
                state = run.get("state")
                run_result = run.get("result")
                if state == "completed":
                    completed += 1
                    if run_result == "succeeded":
                        succeeded += 1
                runs.append(
                    PipelineRunSummary(
                        id=run.get("id"),
                        name=run.get("name"),
                        state=state,
                        result=run_result,
                        created_date=run.get("createdDate"),
                    )
                )
    except AzdoError:
        return PipelineSection()

    pass_rate = round((succeeded / completed) * 100, 1) if completed else None
    return PipelineSection(source="live", runs=runs, pass_rate=pass_rate)


def _pull_request_age_days(created_date: str | None) -> int:
    if not created_date:
        return 0
    try:
        created = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, (datetime.now(timezone.utc) - created).days)


async def collect_pull_requests_section(
    azdo_client: AzdoClient | None,
    persistence: Persistence,
    *,
    repository_id: str,
    limit: int = DEFAULT_PULL_REQUEST_LIMIT,
) -> PullRequestSection:
    """Open pull requests (id, title, age) for the configured repository."""
    if azdo_client is None or not repository_id:
        return PullRequestSection()

    try:
        result = await azdo_tools.list_prs(azdo_client, persistence, repository_id=repository_id)
    except AzdoError:
        return PullRequestSection()

    pull_requests = [
        OpenPullRequestSummary(
            id=pr.get("pullRequestId"),
            title=pr.get("title", ""),
            age_days=_pull_request_age_days(pr.get("creationDate")),
        )
        for pr in result.get("value", [])[:limit]
    ]
    return PullRequestSection(source="live", pull_requests=pull_requests)


async def collect_versions_section(
    persistence: Persistence,
    *,
    seed_infra_path: Path,
    http_fetcher: HttpFetcher = default_http_fetcher,
) -> VersionSection:
    """Current-vs-latest azurerm provider posture, reusing the version-bump detection."""
    try:
        current_constraint = get_current_azurerm_constraint(seed_infra_path)
    except VersionBumpError:
        return VersionSection()

    try:
        version_info = await fetch_latest_provider_version(http_fetcher, persistence)
    except ResearchError:
        return VersionSection()

    bump_needed = not azurerm_constraint_satisfies(version_info.latest_version, current_constraint)
    return VersionSection(
        source="live",
        versions=[
            VersionPosture(
                name="azurerm provider",
                current=current_constraint,
                latest=version_info.latest_version,
                bump_needed=bump_needed,
            )
        ],
    )


def collect_jobs_section(persistence: Persistence, *, recent_limit: int = DEFAULT_RECENT_JOBS_LIMIT) -> JobsSection:
    """Job counts by state, plus recent activity, straight from local persistence."""
    counts = persistence.count_jobs_by_status()
    recent = [
        JobSummary(
            id=row["id"],
            prompt=row["prompt"],
            status=row["status"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
        for row in persistence.list_recent_jobs(recent_limit)
    ]
    return JobsSection(counts_by_status=counts, recent=recent)


def collect_approvals_pending_section(persistence: Persistence) -> ApprovalsPendingSection:
    return ApprovalsPendingSection(count=persistence.count_pending_approvals())


def collect_module_graph(persistence: Persistence) -> ModuleGraphPayload:
    """The real Terraform module graph from the most recent onboarding record."""
    record = persistence.get_latest_onboarding_record()
    if record is None:
        return ModuleGraphPayload()

    return ModuleGraphPayload(
        source="live",
        onboarding_id=record.id,
        repository_path=record.repository_path,
        nodes=[
            ModuleGraphNode(path=node.path, variables=node.variables, outputs=node.outputs)
            for node in record.terraform_module_nodes
        ],
        edges=[
            ModuleGraphEdge(
                caller_path=edge.caller_path,
                module_name=edge.module_name,
                source=edge.source,
                target_path=edge.target_path,
            )
            for edge in record.terraform_module_edges
        ],
    )


# -- orchestration --------------------------------------------------------------------


async def collect_dashboard(
    persistence: Persistence,
    *,
    azdo_client: AzdoClient | None,
    repository_id: str,
    pipeline_ids: list[int],
    seed_infra_path: Path,
    http_fetcher: HttpFetcher = default_http_fetcher,
) -> DashboardPayload:
    pipelines, pull_requests, versions = await asyncio.gather(
        collect_pipelines_section(azdo_client, persistence, pipeline_ids=pipeline_ids),
        collect_pull_requests_section(azdo_client, persistence, repository_id=repository_id),
        collect_versions_section(persistence, seed_infra_path=seed_infra_path, http_fetcher=http_fetcher),
    )
    return DashboardPayload(
        pipelines=pipelines,
        open_pull_requests=pull_requests,
        versions=versions,
        jobs=collect_jobs_section(persistence),
        approvals_pending=collect_approvals_pending_section(persistence),
    )


class DashboardCache:
    """A short in-process TTL cache so repeated dashboard loads don't re-hit AzDO.

    One instance lives on ``app.state`` per app (not a module-level global), so
    tests that build separate apps never see stale results from each other.
    """

    def __init__(self, ttl_seconds: float = 20.0) -> None:
        self._ttl_seconds = ttl_seconds
        self._payload: DashboardPayload | None = None
        self._computed_at: float | None = None

    def get(self, *, now: float) -> DashboardPayload | None:
        if self._payload is None or self._computed_at is None:
            return None
        if (now - self._computed_at) >= self._ttl_seconds:
            return None
        return self._payload

    def set(self, payload: DashboardPayload, *, now: float) -> None:
        self._payload = payload
        self._computed_at = now
