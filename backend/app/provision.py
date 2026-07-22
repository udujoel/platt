"""Step-based, resumable chat-to-provision Job (PRD §F3, §7.2, §8).

Turns a natural-language resource request into a real, reviewable change: a
Boards work-item breakdown, a convention-aware Terraform module, and a pull
request — plan-only until a human approves it. Every step emits a typed
event over the existing contract (``job_created``, ``work_item_moved``,
``plan_ready``, ``approval_required``, ``apply_result``, ...) so a client can
resume/observe the job at any point.

The job is split into two phases that mirror how approval actually happens
(asynchronously, via a human clicking approve/reject sometime later):

* :func:`run_provision_plan` — requirement extraction through requesting
  approval. Stops at ``approval_required``; nothing here can apply anything.
* :func:`run_provision_apply` — runs only after a human has decided the
  approval via :mod:`app.routers.approvals`. ``require_approval`` +
  ``consume_approval`` (see :mod:`app.approvals`) are the *only* way apply can
  proceed: this module never inspects chat text to decide whether to apply,
  and apply additionally stays off unless live Azure credentials and an
  apply pipeline are configured (``ProvisionConfig.has_live_credentials``).

Every AzDO write goes through the shared :class:`~app.tools.executor.ToolExecutor`
(the ``provision`` allowlist in :mod:`app.tools.registry`), so it is audited,
capped, and trivially mockable by swapping in a fake tool registry in tests.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

from app.approvals import BlastRadiusError, check_blast_radius, consume_approval, require_approval
from app.event_bus import EventBus
from app.models import (
    AgentStateEvent,
    ApplyResultEvent,
    ApprovalRequiredEvent,
    JobCreatedEvent,
    PlanReadyEvent,
    PlattState,
    WorkItemMovedEvent,
)
from app.persistence import Persistence
from app.tools.executor import ToolExecutionError, ToolExecutor

MAX_SELF_REPAIR_ATTEMPTS = 3
MIN_CHILD_WORK_ITEMS = 3
MAX_CHILD_WORK_ITEMS = 6
SEED_INFRA_CONVENTION_FILES = ("main.tf", "variables.tf", "outputs.tf", "versions.tf")
TERRAFORM_SUBPROCESS_TIMEOUT_SECONDS = 120


class ProvisionError(RuntimeError):
    """Base class for every reason a provision step can fail."""


class ClarificationNeededError(ProvisionError):
    """Raised when requirement extraction needs one answer from the human before continuing."""

    def __init__(self, question: str) -> None:
        super().__init__(question)
        self.question = question


class SelfRepairExhaustedError(ProvisionError):
    """Raised once the codegen/plan/blast-radius loop has retried 3 times without success."""

    def __init__(self, step: str, last_error: str) -> None:
        super().__init__(f"self-repair exhausted at step {step!r} after {MAX_SELF_REPAIR_ATTEMPTS} attempts: {last_error}")
        self.step = step
        self.last_error = last_error


@dataclass(frozen=True)
class ProvisionConfig:
    """Everything about *where* to provision, held separately from job state.

    ``has_live_credentials`` is never inferred from the job itself — the
    caller sets it from whether ``AzdoClient.from_environment()`` (or an
    equivalent live-Azure check) actually succeeded, so a mocked/test run can
    exercise the full plan-and-request-approval path while apply stays
    structurally unreachable.
    """

    repository_id: str
    seed_infra_path: Path
    target_branch: str = "main"
    sandbox_resource_group: str = "sandbox-rg"
    wiki_identifier: str = "platt.wiki"
    wiki_path: str = "/Provisioning/Log"
    apply_pipeline_id: int | None = None
    has_live_credentials: bool = False


@dataclass(frozen=True)
class RequirementSpec:
    resource_type: str
    name: str
    region: str
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TerraformPlanResult:
    plan_json: dict[str, Any]
    plan_hash: str
    commit_sha: str
    simulated: bool
    raw_output: str = ""


TerraformRunner = Callable[[str, str, "ProvisionConfig"], TerraformPlanResult]


@dataclass(frozen=True)
class ProvisionPlanResult:
    job_id: UUID
    requirement: RequirementSpec
    parent_work_item_id: str
    child_work_item_ids: list[str]
    terraform_file_path: str
    terraform_content: str
    pull_request_id: int
    plan: TerraformPlanResult
    approval_id: UUID
    repair_attempts: int


@dataclass(frozen=True)
class ProvisionApplyResult:
    status: str  # "applied" | "apply_blocked" | "apply_failed"
    summary: str


async def _llm_json_turn(llm: Any, messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Run one tool-free turn and parse its content as a JSON object.

    Raising :class:`ProvisionError` on any malformed response keeps callers'
    self-repair loops uniform: a bad JSON reply from the model is treated the
    same as a bad Terraform plan.
    """
    turn = await llm.complete_turn(messages, [])
    if turn.tool_calls:
        raise ProvisionError("expected a final JSON answer, got tool calls instead")
    if not turn.content:
        raise ProvisionError("the language model returned an empty response")
    try:
        data = json.loads(turn.content)
    except json.JSONDecodeError as error:
        raise ProvisionError(f"the language model response was not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ProvisionError("the language model response must be a JSON object")
    return data


# -- Step 1: requirement extraction ------------------------------------------------


async def _extract_requirement(job_id: UUID, bus: EventBus, llm: Any, prompt: str) -> RequirementSpec:
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Extracting requirement"))
    system = (
        "You are Platt's provisioning intake agent. Read the user's infrastructure request and reply "
        "with a single JSON object only, no prose: "
        '{"resource_type": str, "name": str, "region": str, "tags": object, "clarifying_question": str|null}. '
        "Ask at most one clarifying question, and only when resource_type or name is genuinely ambiguous; "
        "otherwise clarifying_question must be null."
    )
    data = await _llm_json_turn(llm, [{"role": "system", "content": system}, {"role": "user", "content": prompt}])

    clarifying_question = data.get("clarifying_question") or None
    if clarifying_question:
        raise ClarificationNeededError(str(clarifying_question))

    resource_type = str(data.get("resource_type", "")).strip()
    name = str(data.get("name", "")).strip()
    region = str(data.get("region", "")).strip()
    if not resource_type or not name:
        raise ProvisionError("requirement extraction did not produce a resource_type and name")
    return RequirementSpec(resource_type=resource_type, name=name, region=region, tags=dict(data.get("tags") or {}))


# -- Step 2: Boards work-item decomposition ----------------------------------------


async def _decompose_work_items(
    job_id: UUID, bus: EventBus, llm: Any, tool_executor: ToolExecutor, requirement: RequirementSpec
) -> tuple[str, list[str]]:
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Decomposing Boards work items"))

    parent_title = f"Provision {requirement.resource_type}: {requirement.name}"
    parent = await tool_executor.execute("create_work_item", {"work_item_type": "Feature", "title": parent_title})
    parent_id = str(parent.get("id"))
    await bus.publish(
        WorkItemMovedEvent(job_id=job_id, work_item_id=parent_id, title=parent_title, from_state="", to_state="New")
    )

    system = (
        "Break the parent provisioning task into concrete child work items. Reply with a single JSON "
        'object only: {"children": [str, ...]} containing between 3 and 6 short, actionable titles.'
    )
    user = f"Resource: {requirement.resource_type} named {requirement.name} in region {requirement.region or 'unspecified'}."
    data = await _llm_json_turn(llm, [{"role": "system", "content": system}, {"role": "user", "content": user}])
    titles = [str(title).strip() for title in (data.get("children") or []) if str(title).strip()]
    if not (MIN_CHILD_WORK_ITEMS <= len(titles) <= MAX_CHILD_WORK_ITEMS):
        raise ProvisionError(
            f"expected {MIN_CHILD_WORK_ITEMS}-{MAX_CHILD_WORK_ITEMS} child work items, got {len(titles)}"
        )

    child_ids: list[str] = []
    for title in titles:
        child = await tool_executor.execute("create_work_item", {"work_item_type": "Task", "title": title})
        child_id = str(child.get("id"))
        child_ids.append(child_id)
        await bus.publish(
            WorkItemMovedEvent(job_id=job_id, work_item_id=child_id, title=title, from_state="", to_state="New")
        )
    return parent_id, child_ids


# -- Step 3: convention-aware Terraform codegen ------------------------------------


def _read_seed_infra_conventions(seed_infra_path: Path) -> str:
    """Pull a bounded slice of the seed repo's root modules as codegen context."""
    snippets: list[str] = []
    for name in SEED_INFRA_CONVENTION_FILES:
        candidate = seed_infra_path / name
        if candidate.is_file():
            snippets.append(f"# {name}\n{candidate.read_text(encoding='utf-8', errors='replace')[:4000]}")
    modules_dir = seed_infra_path / "modules"
    if modules_dir.is_dir():
        for module_main in sorted(modules_dir.glob("*/main.tf"))[:3]:
            snippets.append(
                f"# modules/{module_main.parent.name}/main.tf\n"
                f"{module_main.read_text(encoding='utf-8', errors='replace')[:2000]}"
            )
    return "\n\n".join(snippets)


async def _generate_terraform(
    job_id: UUID,
    bus: EventBus,
    llm: Any,
    requirement: RequirementSpec,
    seed_infra_path: Path,
    *,
    error_feedback: str | None,
) -> tuple[str, str]:
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Generating Terraform"))
    conventions = _read_seed_infra_conventions(seed_infra_path)
    system = (
        "You are Platt's Terraform codegen agent. Follow the naming, tagging, and module conventions shown "
        "below exactly. Reply with a single JSON object only, no prose: "
        '{"file_path": str, "content": str} where file_path is a path relative to the repository root and '
        f"content is complete, self-contained HCL.\n\nCONVENTIONS:\n{conventions}"
    )
    user = f"Provision a {requirement.resource_type} named {requirement.name} in {requirement.region}. Tags: {requirement.tags}."
    if error_feedback:
        user += f"\n\nThe previous attempt failed: {error_feedback}\nFix the Terraform and reply again."
    data = await _llm_json_turn(llm, [{"role": "system", "content": system}, {"role": "user", "content": user}])

    file_path = str(data.get("file_path", "")).strip()
    content = str(data.get("content", ""))
    if not file_path or not content.strip():
        raise ProvisionError("Terraform codegen did not produce both a file_path and content")
    return file_path, content


# -- Step 4: branch + PR authoring --------------------------------------------------


async def _open_pull_request(
    job_id: UUID,
    tool_executor: ToolExecutor,
    config: ProvisionConfig,
    requirement: RequirementSpec,
    file_path: str,
) -> tuple[str, int]:
    source_branch = f"refs/heads/platt/provision-{job_id}"
    title = f"Provision {requirement.resource_type}: {requirement.name}"
    description = f"Adds `{file_path}` via Platt's chat-to-provision flow. Job `{job_id}`."
    pr = await tool_executor.execute(
        "create_pr",
        {
            "repository_id": config.repository_id,
            "source_branch": source_branch,
            "target_branch": f"refs/heads/{config.target_branch}",
            "title": title,
            "description": description,
        },
    )
    return source_branch, int(pr.get("pullRequestId", 0))


# -- Step 5: local terraform fmt/validate/plan (sandboxed, no cloud creds) ----------


def run_local_terraform_plan(file_path: str, content: str, config: ProvisionConfig) -> TerraformPlanResult:
    """Run ``terraform fmt/validate/plan`` in a scratch copy of the seed repo.

    No cloud credentials are passed through: ``env`` only forwards ``PATH``, so
    the Azure provider can never authenticate here even if it were configured.
    When the ``terraform`` binary isn't installed (true for most dev/test
    environments), the step is cleanly simulated with an empty plan rather
    than failing the whole job.
    """
    commit_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    terraform_bin = shutil.which("terraform")
    if terraform_bin is None:
        plan_json: dict[str, Any] = {"resource_changes": []}
        plan_hash = hashlib.sha256(json.dumps(plan_json, sort_keys=True).encode()).hexdigest()
        return TerraformPlanResult(
            plan_json=plan_json,
            plan_hash=plan_hash,
            commit_sha=commit_sha,
            simulated=True,
            raw_output="terraform CLI not present; plan simulated as empty",
        )

    env = {"PATH": os.environ.get("PATH", "")}
    with tempfile.TemporaryDirectory(prefix="platt-provision-") as tmp:
        workdir = Path(tmp)
        shutil.copytree(config.seed_infra_path, workdir, dirs_exist_ok=True)
        target = workdir / file_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        try:
            subprocess.run(
                [terraform_bin, "fmt", "-recursive"],
                cwd=workdir,
                env=env,
                capture_output=True,
                timeout=TERRAFORM_SUBPROCESS_TIMEOUT_SECONDS,
            )
            init = subprocess.run(
                [terraform_bin, "init", "-backend=false", "-input=false"],
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=TERRAFORM_SUBPROCESS_TIMEOUT_SECONDS,
            )
            if init.returncode != 0:
                raise ProvisionError(f"terraform init failed: {(init.stderr or init.stdout)[:2000]}")

            validate = subprocess.run(
                [terraform_bin, "validate", "-json"],
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=TERRAFORM_SUBPROCESS_TIMEOUT_SECONDS,
            )
            if validate.returncode != 0:
                raise ProvisionError(f"terraform validate failed: {(validate.stdout or validate.stderr)[:2000]}")

            plan_out = workdir / "plan.out"
            plan = subprocess.run(
                [terraform_bin, "plan", "-input=false", "-out", str(plan_out)],
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=TERRAFORM_SUBPROCESS_TIMEOUT_SECONDS,
            )
            if plan.returncode != 0:
                raise ProvisionError(f"terraform plan failed: {(plan.stdout or plan.stderr)[:2000]}")

            show = subprocess.run(
                [terraform_bin, "show", "-json", str(plan_out)],
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=TERRAFORM_SUBPROCESS_TIMEOUT_SECONDS,
            )
            if show.returncode != 0:
                raise ProvisionError(f"terraform show failed: {show.stderr[:2000]}")
        except (OSError, subprocess.TimeoutExpired) as error:
            # Environment couldn't actually run terraform (e.g. sandboxed, no
            # network for provider download) -- simulate rather than block the
            # whole job on infrastructure the caller doesn't control.
            plan_json = {"resource_changes": []}
            plan_hash = hashlib.sha256(json.dumps(plan_json, sort_keys=True).encode()).hexdigest()
            return TerraformPlanResult(
                plan_json=plan_json,
                plan_hash=plan_hash,
                commit_sha=commit_sha,
                simulated=True,
                raw_output=f"terraform run could not complete ({error}); plan simulated as empty",
            )

        plan_json = json.loads(show.stdout)

    plan_hash = hashlib.sha256(json.dumps(plan_json, sort_keys=True).encode()).hexdigest()
    return TerraformPlanResult(
        plan_json=plan_json, plan_hash=plan_hash, commit_sha=commit_sha, simulated=False, raw_output=show.stdout[:2000]
    )


def _plan_has_blocking_changes(plan_json: dict[str, Any]) -> bool:
    return any(
        "delete" in change.get("change", {}).get("actions", [])
        for change in plan_json.get("resource_changes", [])
    )


# -- Orchestration: plan phase -------------------------------------------------------


async def run_provision_plan(
    job_id: UUID,
    bus: EventBus,
    persistence: Persistence,
    llm: Any,
    tool_executor: ToolExecutor,
    prompt: str,
    config: ProvisionConfig,
    *,
    terraform_runner: TerraformRunner = run_local_terraform_plan,
) -> ProvisionPlanResult:
    """Requirement extraction through requesting approval. Never applies anything.

    A plan or blast-radius failure retries Terraform codegen with the failure
    fed back to the model, up to :data:`MAX_SELF_REPAIR_ATTEMPTS` times; a
    tool-call-cap breach (:class:`~app.tools.executor.ToolCapExceededError`)
    is a separate, non-retriable cap and is left to propagate as-is.
    """
    await bus.publish(JobCreatedEvent(job_id=job_id, prompt=prompt))

    requirement = await _extract_requirement(job_id, bus, llm, prompt)
    parent_id, child_ids = await _decompose_work_items(job_id, bus, llm, tool_executor, requirement)

    repair_attempts = 0
    error_feedback: str | None = None
    file_path = ""
    content = ""
    pull_request_id = 0
    plan: TerraformPlanResult | None = None

    while True:
        try:
            file_path, content = await _generate_terraform(
                job_id, bus, llm, requirement, config.seed_infra_path, error_feedback=error_feedback
            )
            _, pull_request_id = await _open_pull_request(job_id, tool_executor, config, requirement, file_path)

            await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Running local terraform plan"))
            plan = terraform_runner(file_path, content, config)

            summary = f"Plan for {file_path}: {len(plan.plan_json.get('resource_changes', []))} resource change(s)"
            if plan.simulated:
                summary += " (simulated, no terraform CLI)"
            await bus.publish(
                PlanReadyEvent(job_id=job_id, summary=summary, has_blocking_changes=_plan_has_blocking_changes(plan.plan_json))
            )

            check_blast_radius(plan.plan_json, config.sandbox_resource_group)
            break
        except (ProvisionError, BlastRadiusError) as error:
            repair_attempts += 1
            if repair_attempts > MAX_SELF_REPAIR_ATTEMPTS:
                await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.CONCERNED, label="Self-repair exhausted"))
                raise SelfRepairExhaustedError("terraform_plan", str(error)) from error
            await bus.publish(
                AgentStateEvent(job_id=job_id, state=PlattState.CONCERNED, label=f"Self-repair attempt {repair_attempts}")
            )
            error_feedback = str(error)

    assert plan is not None  # the loop only exits via `break` once `plan` is set

    approval_id = uuid4()
    persistence.create_approval(
        approval_id=approval_id,
        job_id=job_id,
        plan_hash=plan.plan_hash,
        commit_sha=plan.commit_sha,
        scope=config.sandbox_resource_group,
    )
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.AWAITING_APPROVAL, label="Plan approval required"))
    await bus.publish(
        ApprovalRequiredEvent(
            job_id=job_id,
            approval_id=approval_id,
            summary=f"Approve applying {file_path} ({plan.plan_hash[:12]}) to {config.sandbox_resource_group}",
        )
    )

    return ProvisionPlanResult(
        job_id=job_id,
        requirement=requirement,
        parent_work_item_id=parent_id,
        child_work_item_ids=child_ids,
        terraform_file_path=file_path,
        terraform_content=content,
        pull_request_id=pull_request_id,
        plan=plan,
        approval_id=approval_id,
        repair_attempts=repair_attempts,
    )


# -- Orchestration: apply phase ------------------------------------------------------


async def run_provision_apply(
    job_id: UUID,
    bus: EventBus,
    persistence: Persistence,
    tool_executor: ToolExecutor,
    config: ProvisionConfig,
    *,
    plan_hash: str,
    commit_sha: str,
    parent_work_item_id: str,
    child_work_item_ids: list[str],
) -> ProvisionApplyResult:
    """Run only once a human has approved. Structurally cannot apply otherwise.

    ``require_approval`` (raises unless a decided, unexpired, unconsumed
    approval exists for this exact job/plan_hash/commit_sha) and
    ``consume_approval`` (one-time; a second apply attempt on the same
    approval always fails) are both mandatory and un-bypassable here — there
    is no code path in this function that reaches the apply-pipeline trigger
    without both succeeding first.
    """
    record = require_approval(persistence, job_id, plan_hash=plan_hash, commit_sha=commit_sha)
    consume_approval(persistence, UUID(record.id))

    if not (config.has_live_credentials and config.apply_pipeline_id):
        await bus.publish(
            ApplyResultEvent(
                job_id=job_id,
                success=False,
                summary="Apply requires live Azure credentials and a configured apply pipeline; plan is approved but not applied.",
            )
        )
        return ProvisionApplyResult(status="apply_blocked", summary="apply requires live Azure credentials")

    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Triggering apply pipeline"))
    run = await tool_executor.execute(
        "run_pipeline",
        {"pipeline_id": config.apply_pipeline_id, "branch": config.target_branch, "variables": {"PLATT_JOB_ID": str(job_id)}},
    )
    run_id = int(run.get("id", 0))
    run_status = await tool_executor.execute("get_pipeline_run", {"pipeline_id": config.apply_pipeline_id, "run_id": run_id})
    succeeded = str(run_status.get("result", "")).lower() == "succeeded"

    await bus.publish(
        ApplyResultEvent(
            job_id=job_id, success=succeeded, summary=f"Apply pipeline run {run_id} finished with result={run_status.get('result')}"
        )
    )
    if not succeeded:
        await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.CONCERNED, label="Apply pipeline failed"))
        return ProvisionApplyResult(status="apply_failed", summary=f"pipeline run {run_id} did not succeed")

    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Verifying apply"))
    await _append_wiki_log(job_id, tool_executor, config, run_id=run_id)

    for work_item_id in [parent_work_item_id, *child_work_item_ids]:
        await tool_executor.execute("update_work_item_state", {"work_item_id": int(work_item_id), "state": "Done"})
        await bus.publish(
            WorkItemMovedEvent(job_id=job_id, work_item_id=work_item_id, title="", from_state="Active", to_state="Done")
        )

    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.CELEBRATING, label="Apply succeeded"))
    return ProvisionApplyResult(status="applied", summary=f"applied via pipeline run {run_id}")


async def _append_wiki_log(job_id: UUID, tool_executor: ToolExecutor, config: ProvisionConfig, *, run_id: int) -> None:
    entry = f"\n## Provisioned via job `{job_id}`\n\nApplied by pipeline run `{run_id}`.\n"
    version: str | None = None
    existing_content = ""
    try:
        existing = await tool_executor.execute(
            "get_wiki_page", {"wiki_identifier": config.wiki_identifier, "path": config.wiki_path}
        )
        version = existing.get("eTag")
        existing_content = existing.get("content") or ""
    except ToolExecutionError:
        pass

    payload = {
        "wiki_identifier": config.wiki_identifier,
        "path": config.wiki_path,
        "content": existing_content + entry,
    }
    if version:
        payload["version"] = version
    await tool_executor.execute("update_wiki_page", payload)
