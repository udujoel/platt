from uuid import uuid4

from fastapi import APIRouter, Request

from app.background_tasks import create_background_task
from app.event_bus import event_bus
from app.jobs import stream_chat_job
from app.llm import create_llm_from_environment
from app.models import ChatRequest, ChatResponse, JobCreatedEvent

router = APIRouter(tags=["chat"])


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
    create_background_task(
        request.app,
        stream_chat_job(
            job_id=job_id,
            bus=event_bus,
            llm=create_llm_from_environment(),
            prompt=chat_request.prompt,
        ),
    )
    return ChatResponse(job_id=job_id)
