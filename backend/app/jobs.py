import asyncio
from uuid import UUID

from app.event_bus import EventBus
from app.models import AgentStateEvent, ChatDeltaEvent, PlattState


FAKE_TOKENS = ("I", " can", " see", " the", " Phase", " 1", " event", " contract.")


async def stream_fake_chat_job(job_id: UUID, bus: EventBus, delay_seconds: float = 0.01) -> None:
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Planning response"))

    for index, token in enumerate(FAKE_TOKENS):
        await asyncio.sleep(delay_seconds)
        await bus.publish(ChatDeltaEvent(job_id=job_id, delta=token, index=index))

    await bus.publish(ChatDeltaEvent(job_id=job_id, delta="", index=len(FAKE_TOKENS), done=True))
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.IDLE, label="Ready"))

