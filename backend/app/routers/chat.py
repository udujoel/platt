import asyncio
from uuid import uuid4

from fastapi import APIRouter

from app.event_bus import event_bus
from app.jobs import stream_fake_chat_job
from app.models import ChatRequest, ChatResponse, JobCreatedEvent

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse, status_code=202)
async def chat(request: ChatRequest) -> ChatResponse:
    job_id = uuid4()
    await event_bus.publish(JobCreatedEvent(job_id=job_id, prompt=request.prompt))
    asyncio.create_task(stream_fake_chat_job(job_id=job_id, bus=event_bus))
    return ChatResponse(job_id=job_id)

