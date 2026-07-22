from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request

from app.background_tasks import create_background_task
from app.clients.azdo import AzdoClient, AzdoNotConfiguredError
from app.event_bus import event_bus
from app.jobs import stream_chat_job
from app.llm import create_llm_from_environment
from app.models import ChatRequest, ChatResponse, JobCreatedEvent
from app.tools.executor import ToolExecutor
from app.tools.registry import DEFAULT_REGISTRY, JOB_ALLOWLISTS

router = APIRouter(tags=["chat"])


async def _run_and_close(job: Any, azdo_client: AzdoClient | None) -> None:
    try:
        await job
    finally:
        if azdo_client is not None:
            await azdo_client.aclose()


@router.post("/chat", response_model=ChatResponse, status_code=202)
async def chat(request: Request, chat_request: ChatRequest) -> ChatResponse:
    job_id = uuid4()
    request.app.state.persistence.record_job(job_id=job_id, prompt=chat_request.prompt)
    request.app.state.persistence.record_audit_entry(
        job_id=job_id,
        tool="chat",
        action="create_job",
        outcome="accepted",
    )
    await event_bus.publish(JobCreatedEvent(job_id=job_id, prompt=chat_request.prompt))

    azdo_client: AzdoClient | None = None
    tool_names: tuple[str, ...] = ()
    resources: dict[str, Any] = {}
    try:
        azdo_client = AzdoClient.from_environment()
        tool_names = tuple(JOB_ALLOWLISTS["chat"])
        resources = {"azdo_client": azdo_client}
    except AzdoNotConfiguredError:
        pass

    tool_executor = ToolExecutor(
        DEFAULT_REGISTRY,
        request.app.state.persistence,
        JOB_ALLOWLISTS["chat"],
        job_id=job_id,
        event_bus=event_bus,
        resources=resources,
    )

    create_background_task(
        request.app,
        _run_and_close(
            stream_chat_job(
                job_id=job_id,
                bus=event_bus,
                llm=create_llm_from_environment(),
                prompt=chat_request.prompt,
                tool_executor=tool_executor,
                tool_names=tool_names,
            ),
            azdo_client,
        ),
    )
    return ChatResponse(job_id=job_id)
