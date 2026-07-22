"""HTTP entry points for the autonomous version-bump Job (PRD §F4).

``POST /version-bump/trigger`` runs the full detect -> assess -> bump -> plan
-> PR flow once in the background, exactly like any other job (Platt goes
``working`` while it runs and emits the same typed events). ``GET
/version-bump/schedule`` reports the cadence Platt intends to run on; wiring
an actual scheduler (cron, an Azure Function timer trigger, ...) to call the
trigger endpoint is left to deployment configuration -- this is a stub
describing the intent, not a running scheduler.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.background_tasks import create_background_task
from app.clients.azdo import AzdoClient, AzdoNotConfiguredError
from app.event_bus import event_bus
from app.llm import create_llm_from_environment
from app.models import ChatResponse
from app.tools.executor import ToolExecutor
from app.tools.registry import DEFAULT_REGISTRY, JOB_ALLOWLISTS
from app.version_bump import VersionBumpConfig, run_version_bump_check

router = APIRouter(prefix="/version-bump", tags=["version-bump"])

# Not wired to a real scheduler -- see module docstring.
VERSION_BUMP_SCHEDULE_CRON = "0 6 * * 1"  # every Monday at 06:00 UTC


class VersionBumpScheduleResponse(BaseModel):
    cron: str
    description: str
    wired: bool = False


def _seed_infra_path() -> Path:
    return Path(__file__).resolve().parents[3] / "seed-infra"


@router.get("/schedule", response_model=VersionBumpScheduleResponse)
async def get_schedule() -> VersionBumpScheduleResponse:
    return VersionBumpScheduleResponse(
        cron=VERSION_BUMP_SCHEDULE_CRON,
        description="Weekly azurerm provider release check (stub; not yet wired to a scheduler).",
    )


@router.post("/trigger", response_model=ChatResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_version_bump(request: Request) -> ChatResponse:
    job_id = uuid4()
    persistence = request.app.state.persistence
    persistence.record_job(job_id=job_id, prompt="Automated version-bump check")

    try:
        azdo_client = AzdoClient.from_environment()
    except AzdoNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure DevOps is not configured; version-bump PRs need the AzDO connector.",
        ) from None

    config = VersionBumpConfig(
        repository_id=request.app.state.provision_repository_id,
        seed_infra_path=_seed_infra_path(),
    )
    tool_executor = ToolExecutor(
        DEFAULT_REGISTRY,
        persistence,
        JOB_ALLOWLISTS["version_bump"],
        job_id=job_id,
        event_bus=event_bus,
        resources={"azdo_client": azdo_client},
    )

    async def _job() -> None:
        try:
            await run_version_bump_check(
                job_id=job_id,
                bus=event_bus,
                persistence=persistence,
                tool_executor=tool_executor,
                llm=create_llm_from_environment(),
                config=config,
            )
        finally:
            await azdo_client.aclose()

    create_background_task(request.app, _job())
    return ChatResponse(job_id=job_id)
