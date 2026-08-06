"""Autonomous version-bump Job (PRD §F4).

Checks whether the ``azurerm`` Terraform provider constraint pinned in
``seed-infra/versions.tf`` is behind the latest release on the public
Terraform Registry, asks the LLM to assess how risky adopting it is, and --
only when a bump is actually warranted -- opens a plan-only PR with an
AI-written description and recommendation.

This job never applies anything: its Terraform step is exactly the same
sandboxed fmt/validate/plan helper the chat-to-provision job uses (see
:func:`app.provision.run_local_terraform_plan`), which never runs against
live Azure credentials. Every AzDO write goes through the shared
:class:`~app.tools.executor.ToolExecutor` (the ``version_bump`` allowlist in
:mod:`app.tools.registry`), same audit/cap guarantees as provisioning.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.event_bus import EventBus
from app.models import (
    AgentStateEvent,
    JobCreatedEvent,
    PlanReadyEvent,
    PlattState,
    ReleaseDetectedEvent,
    SignificanceAssessedEvent,
)
from app.persistence import Persistence
from app.provision import ProvisionConfig, TerraformPlanResult, TerraformRunner, run_local_terraform_plan
from app.tools.executor import ToolExecutor
from app.tools.research import (
    HttpFetcher,
    default_http_fetcher,
    fetch_latest_provider_version,
    fetch_provider_release_notes,
)

VERSIONS_TF_FILE = "versions.tf"
VALID_RECOMMENDATIONS = ("merge now", "merge with caution", "hold")

# Matches the `azurerm = { source = "...", version = "..." }` block in
# versions.tf; group 2 is the quoted constraint text this module reads/bumps.
_CONSTRAINT_PATTERN = re.compile(r'(azurerm\s*=\s*\{[^}]*?version\s*=\s*")([^"]+)(")', re.DOTALL)


class VersionBumpError(RuntimeError):
    """Base class for every reason a version-bump job step can fail."""


@dataclass(frozen=True)
class VersionBumpConfig:
    repository_id: str
    seed_infra_path: Path
    target_branch: str = "main"
    provider_namespace: str = "hashicorp"
    provider_name: str = "azurerm"
    github_org: str = "hashicorp"
    github_repo: str = "terraform-provider-azurerm"


@dataclass(frozen=True)
class SignificanceAssessment:
    recommendation: str
    reasoning: str


@dataclass(frozen=True)
class VersionBumpResult:
    job_id: UUID
    bumped: bool
    current_constraint: str
    latest_version: str
    new_constraint: str | None = None
    pull_request_id: int | None = None
    plan: TerraformPlanResult | None = None
    assessment: SignificanceAssessment | None = None


# -- versions.tf parsing / constraint math -------------------------------------------


def _read_versions_file(seed_infra_path: Path) -> tuple[str, str]:
    """Return ``(file content, current azurerm version constraint)``."""
    path = seed_infra_path / VERSIONS_TF_FILE
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        raise VersionBumpError(f"could not read {VERSIONS_TF_FILE}: {error}") from error
    match = _CONSTRAINT_PATTERN.search(content)
    if match is None:
        raise VersionBumpError(f"no azurerm provider version constraint found in {VERSIONS_TF_FILE}")
    return content, match.group(2)


def _parse_version(version: str) -> tuple[int, ...]:
    core = version.split("-", 1)[0].split("+", 1)[0]
    try:
        return tuple(int(part) for part in core.split("."))
    except ValueError as error:
        raise VersionBumpError(f"not a parseable version: {version!r}") from error


def _normalize(parts: tuple[int, ...], length: int = 3) -> tuple[int, ...]:
    return (parts + (0,) * length)[:length]


def _parse_pessimistic_constraint(constraint: str) -> tuple[int, ...]:
    match = re.match(r"~>\s*([\d.]+)$", constraint.strip())
    if match is None:
        raise VersionBumpError(f"unsupported constraint format (only \"~>\" is supported): {constraint!r}")
    parts = _parse_version(match.group(1))
    if len(parts) not in (2, 3):
        raise VersionBumpError(f"unsupported constraint precision: {constraint!r}")
    return parts


def _pessimistic_constraint_allows(version: str, constraint: str) -> bool:
    """Whether ``version`` satisfies a Terraform ``~>`` pessimistic constraint.

    ``~> 4.0`` allows any ``4.x`` (>=4.0, <5.0); ``~> 4.0.0`` allows any
    ``4.0.x`` (>=4.0.0, <4.1.0).
    """
    constraint_parts = _parse_pessimistic_constraint(constraint)
    if len(constraint_parts) == 2:
        floor = _normalize(constraint_parts)
        ceiling = _normalize((constraint_parts[0] + 1,))
    else:
        floor = _normalize(constraint_parts)
        ceiling = _normalize((constraint_parts[0], constraint_parts[1] + 1))
    version_norm = _normalize(_parse_version(version))
    return floor <= version_norm < ceiling


def _bump_constraint(latest_version: str, constraint: str) -> str:
    """A new ``~>`` constraint covering ``latest_version``, same precision as the original."""
    constraint_parts = _parse_pessimistic_constraint(constraint)
    latest_parts = _parse_version(latest_version)
    if len(constraint_parts) == 2:
        return f"~> {latest_parts[0]}.0"
    minor = latest_parts[1] if len(latest_parts) > 1 else 0
    return f"~> {latest_parts[0]}.{minor}.0"


def _version_bump_branch_name(job_id: UUID) -> str:
    return f"platt/version-bump-{job_id}"


def get_current_azurerm_constraint(seed_infra_path: Path) -> str:
    """The pinned azurerm constraint, for callers outside this module (e.g. the dashboard collector)."""
    return _read_versions_file(seed_infra_path)[1]


def azurerm_constraint_satisfies(version: str, constraint: str) -> bool:
    """Public wrapper around the same pessimistic-constraint check the job uses."""
    return _pessimistic_constraint_allows(version, constraint)


# -- significance assessment ----------------------------------------------------------


async def _assess_significance(
    llm: Any, *, current_constraint: str, latest_version: str, release_notes: str
) -> SignificanceAssessment:
    system = (
        "You are Platt's version-bump risk assessor. Given a Terraform provider's current "
        "version constraint, the latest available release, and its release notes, reply with "
        'a single JSON object only, no prose: {"recommendation": str, "reasoning": str}. '
        f"\"recommendation\" must be exactly one of {list(VALID_RECOMMENDATIONS)!r}."
    )
    user = (
        f"Current constraint: {current_constraint}\nLatest version: {latest_version}\n\n"
        f"Release notes:\n{release_notes or '(no release notes available)'}"
    )
    turn = await llm.complete_turn([{"role": "system", "content": system}, {"role": "user", "content": user}], [])
    if turn.tool_calls:
        raise VersionBumpError("expected a final JSON answer, got tool calls instead")
    if not turn.content:
        raise VersionBumpError("the language model returned an empty response")
    try:
        data = json.loads(turn.content)
    except json.JSONDecodeError as error:
        raise VersionBumpError(f"the language model response was not valid JSON: {error}") from error

    recommendation = str(data.get("recommendation", "")).strip().lower()
    if recommendation not in VALID_RECOMMENDATIONS:
        raise VersionBumpError(f"unexpected recommendation value: {recommendation!r}")
    reasoning = str(data.get("reasoning", "")).strip()
    if not reasoning:
        raise VersionBumpError("significance assessment did not include reasoning")
    return SignificanceAssessment(recommendation=recommendation, reasoning=reasoning)


# -- branch / PR authoring -------------------------------------------------------------


async def _push_version_bump(
    tool_executor: ToolExecutor, config: VersionBumpConfig, *, branch_name: str, content: str
) -> None:
    base_branch = await tool_executor.execute(
        "get_branch", {"repository_id": config.repository_id, "branch_name": config.target_branch}
    )
    if base_branch is None:
        raise VersionBumpError(f"base branch not found: {config.target_branch!r}")
    await tool_executor.execute(
        "push_file",
        {
            "repository_id": config.repository_id,
            "branch_name": branch_name,
            "base_object_id": base_branch["objectId"],
            "file_path": VERSIONS_TF_FILE,
            "content": content,
            "change_type": "edit",
            "comment": "Platt: bump azurerm provider constraint",
        },
    )


def _pr_description(
    *,
    config: VersionBumpConfig,
    current_constraint: str,
    new_constraint: str,
    latest_version: str,
    plan_summary: str,
    assessment: SignificanceAssessment,
) -> str:
    return (
        "## Automated version bump\n\n"
        f"- Provider: `{config.provider_namespace}/{config.provider_name}`\n"
        f"- Current constraint: `{current_constraint}`\n"
        f"- Latest release: `{latest_version}`\n"
        f"- New constraint: `{new_constraint}`\n\n"
        "## Plan\n\n"
        f"{plan_summary}\n\n"
        f"## Recommendation: {assessment.recommendation}\n\n"
        f"{assessment.reasoning}\n\n"
        "This PR is plan-only; nothing has been applied. Review the recommendation above before merging."
    )


async def _open_version_bump_pr(
    tool_executor: ToolExecutor,
    config: VersionBumpConfig,
    *,
    branch_name: str,
    description: str,
    new_constraint: str,
    current_constraint: str,
) -> int:
    title = f"Bump azurerm provider: {current_constraint} -> {new_constraint}"
    pr = await tool_executor.execute(
        "create_pr",
        {
            "repository_id": config.repository_id,
            "source_branch": f"refs/heads/{branch_name}",
            "target_branch": f"refs/heads/{config.target_branch}",
            "title": title,
            "description": description,
        },
    )
    return int(pr.get("pullRequestId", 0))


# -- orchestration ----------------------------------------------------------------------


async def run_version_bump_check(
    job_id: UUID,
    bus: EventBus,
    persistence: Persistence,
    tool_executor: ToolExecutor,
    llm: Any,
    config: VersionBumpConfig,
    *,
    http_fetcher: HttpFetcher = default_http_fetcher,
    terraform_runner: TerraformRunner = run_local_terraform_plan,
) -> VersionBumpResult:
    """Detect -> assess -> bump -> plan -> PR. Never applies anything.

    Returns early (``bumped=False``, no PR) when the latest release already
    satisfies the pinned constraint.
    """
    dependency = f"{config.provider_namespace}/{config.provider_name}"
    await bus.publish(JobCreatedEvent(job_id=job_id, prompt=f"Automated version-bump check: {dependency}"))
    await bus.publish(
        AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Checking Terraform Registry for a newer release")
    )

    content, current_constraint = _read_versions_file(config.seed_infra_path)

    version_info = await fetch_latest_provider_version(
        http_fetcher,
        persistence,
        namespace=config.provider_namespace,
        name=config.provider_name,
        job_id=job_id,
        event_bus=bus,
    )
    latest_version = version_info.latest_version
    bump_needed = not _pessimistic_constraint_allows(latest_version, current_constraint)

    await bus.publish(
        ReleaseDetectedEvent(
            job_id=job_id,
            dependency=dependency,
            current_constraint=current_constraint,
            latest_version=latest_version,
            bump_needed=bump_needed,
        )
    )

    if not bump_needed:
        await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.IDLE, label="No version bump needed"))
        return VersionBumpResult(
            job_id=job_id, bumped=False, current_constraint=current_constraint, latest_version=latest_version
        )

    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Assessing release significance"))
    release_notes = await fetch_provider_release_notes(
        http_fetcher,
        persistence,
        org=config.github_org,
        repo=config.github_repo,
        version=latest_version,
        job_id=job_id,
        event_bus=bus,
    )
    assessment = await _assess_significance(
        llm, current_constraint=current_constraint, latest_version=latest_version, release_notes=release_notes
    )
    await bus.publish(
        SignificanceAssessedEvent(job_id=job_id, recommendation=assessment.recommendation, reasoning=assessment.reasoning)
    )

    new_constraint = _bump_constraint(latest_version, current_constraint)
    new_content = _CONSTRAINT_PATTERN.sub(rf"\g<1>{new_constraint}\g<3>", content, count=1)

    branch_name = _version_bump_branch_name(job_id)
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Pushing version bump"))
    await _push_version_bump(tool_executor, config, branch_name=branch_name, content=new_content)

    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Running local terraform plan"))
    # terraform_runner shells out via blocking subprocess.run (fmt/validate/plan);
    # run it off the event loop so a slow Terraform run doesn't stall other
    # in-flight requests sharing this process's asyncio loop.
    plan = await asyncio.to_thread(
        terraform_runner,
        VERSIONS_TF_FILE,
        new_content,
        ProvisionConfig(
            repository_id=config.repository_id, seed_infra_path=config.seed_infra_path, target_branch=config.target_branch
        ),
    )
    plan_summary = (
        f"Plan for bumping azurerm {current_constraint} -> {new_constraint}: "
        f"{len(plan.plan_json.get('resource_changes', []))} resource change(s)"
    )
    if plan.simulated:
        plan_summary += " (simulated, no terraform CLI)"
    await bus.publish(PlanReadyEvent(job_id=job_id, summary=plan_summary, has_blocking_changes=False))

    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Opening version-bump PR"))
    description = _pr_description(
        config=config,
        current_constraint=current_constraint,
        new_constraint=new_constraint,
        latest_version=latest_version,
        plan_summary=plan_summary,
        assessment=assessment,
    )
    pull_request_id = await _open_version_bump_pr(
        tool_executor,
        config,
        branch_name=branch_name,
        description=description,
        new_constraint=new_constraint,
        current_constraint=current_constraint,
    )

    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.CELEBRATING, label="Version-bump PR opened"))

    return VersionBumpResult(
        job_id=job_id,
        bumped=True,
        current_constraint=current_constraint,
        latest_version=latest_version,
        new_constraint=new_constraint,
        pull_request_id=pull_request_id,
        plan=plan,
        assessment=assessment,
    )
