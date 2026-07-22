"""HTTP entry points for the chat-to-provision Job (PRD §F3).

Mirrors the two-phase split in :mod:`app.provision`: ``POST /provision``
starts the plan-only phase (through ``approval_required``); once a human
decides that approval via :mod:`app.routers.approvals`, ``POST
/provision/{job_id}/apply`` runs the apply phase, which is structurally
gated on that decision (see ``app.approvals.require_approval``).

Plan output needed to resume into the apply phase (plan_hash, commit_sha,
work item ids) is kept in an in-process dict on ``app.state`` rather than a
new table: it is disposable job-run scratch state, not a durable record --
the approval itself is what is durably recorded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.background_tasks import create_background_task
from app.clients.azdo import AzdoClient, AzdoNotConfiguredError
from app.event_bus import event_bus
from app.llm import create_llm_from_environment
from app.models import ChatRequest, ChatResponse
from app.provision import ProvisionConfig, run_provision_apply, run_provision_plan
from app.tools.executor import ToolExecutor
from app.tools.registry import DEFAULT_REGISTRY, JOB_ALLOWLISTS

router = APIRouter(prefix="/provision", tags=["provision"])


class ProvisionApplyRequest(BaseModel):
    plan_hash: str = Field(min_length=1, max_length=256)
    commit_sha: str = Field(min_length=1, max_length=256)


def _seed_infra_path() -> Path:
    return Path(__file__).resolve().parents[3] / "seed-infra"


async def _run_plan_and_close(job: Any, azdo_client: AzdoClient) -> None:
    try:
        await job
    finally:
        await azdo_client.aclose()


@router.post("", response_model=ChatResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_provision(request: Request, chat_request: ChatRequest) -> ChatResponse:
    job_id = uuid4()
    persistence = request.app.state.persistence
    persistence.record_job(job_id=job_id, prompt=chat_request.prompt)

    try:
        azdo_client = AzdoClient.from_environment()
        has_live_credentials = True
    except AzdoNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure DevOps is not configured; provisioning needs the AzDO connector even for plan-only runs.",
        ) from None

    config = ProvisionConfig(
        repository_id=request.app.state.provision_repository_id,
        seed_infra_path=_seed_infra_path(),
        has_live_credentials=has_live_credentials,
        apply_pipeline_id=request.app.state.provision_apply_pipeline_id,
    )
    tool_executor = ToolExecutor(
        DEFAULT_REGISTRY,
        persistence,
        JOB_ALLOWLISTS["provision"],
        job_id=job_id,
        event_bus=event_bus,
        resources={"azdo_client": azdo_client},
    )

    async def _plan_job() -> None:
        result = await run_provision_plan(
            job_id=job_id,
            bus=event_bus,
            persistence=persistence,
            llm=create_llm_from_environment(),
            tool_executor=tool_executor,
            prompt=chat_request.prompt,
            config=config,
        )
        request.app.state.provision_jobs[job_id] = {
            "plan_hash": result.plan.plan_hash,
            "commit_sha": result.plan.commit_sha,
            "parent_work_item_id": result.parent_work_item_id,
            "child_work_item_ids": result.child_work_item_ids,
            "config": config,
        }

    create_background_task(request.app, _run_plan_and_close(_plan_job(), azdo_client))
    return ChatResponse(job_id=job_id)


@router.post("/{job_id}/apply", status_code=status.HTTP_202_ACCEPTED)
async def apply_provision(request: Request, job_id: UUID, payload: ProvisionApplyRequest) -> dict:
    state = request.app.state.provision_jobs.get(job_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no provision plan found for this job")

    persistence = request.app.state.persistence
    config: ProvisionConfig = state["config"]
    try:
        azdo_client = AzdoClient.from_environment()
    except AzdoNotConfiguredError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Azure DevOps is not configured.") from None

    tool_executor = ToolExecutor(
        DEFAULT_REGISTRY,
        persistence,
        JOB_ALLOWLISTS["provision"],
        job_id=job_id,
        event_bus=event_bus,
        resources={"azdo_client": azdo_client},
    )

    async def _apply_job() -> None:
        await run_provision_apply(
            job_id=job_id,
            bus=event_bus,
            persistence=persistence,
            tool_executor=tool_executor,
            config=config,
            plan_hash=payload.plan_hash,
            commit_sha=payload.commit_sha,
            parent_work_item_id=state["parent_work_item_id"],
            child_work_item_ids=state["child_work_item_ids"],
        )

    create_background_task(request.app, _run_plan_and_close(_apply_job(), azdo_client))
    return {"status": "accepted", "job_id": str(job_id)}
