import asyncio
from uuid import UUID

from app.event_bus import EventBus
from app.models import AgentStateEvent, ChatDeltaEvent, PlattState


FAKE_TOKENS = ("I", " can", " see", " the", " Phase", " 1", " event", " contract.")
DEV_STATE_SEQUENCE = (
    (PlattState.LISTENING, "Chat input focused"),
    (PlattState.THINKING, "Planning response"),
    (PlattState.WORKING, "Tool execution in flight"),
    (PlattState.TALKING, "Streaming response"),
    (PlattState.AWAITING_APPROVAL, "Plan approval required"),
    (PlattState.CELEBRATING, "Apply succeeded"),
    (PlattState.CONCERNED, "Pipeline error detected"),
    (PlattState.IDLE, "Returned to idle"),
)


async def stream_fake_chat_job(job_id: UUID, bus: EventBus, delay_seconds: float = 0.01) -> None:
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Planning response"))

    for index, token in enumerate(FAKE_TOKENS):
        await asyncio.sleep(delay_seconds)
        if index == 1:
            await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.TALKING, label="Streaming response"))
        await bus.publish(ChatDeltaEvent(job_id=job_id, delta=token, index=index))

    await bus.publish(ChatDeltaEvent(job_id=job_id, delta="", index=len(FAKE_TOKENS), done=True))
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.IDLE, label="Ready"))


async def stream_dev_state_cycle(job_id: UUID, bus: EventBus, delay_seconds: float = 0.35) -> None:
    for state, label in DEV_STATE_SEQUENCE:
        await bus.publish(AgentStateEvent(job_id=job_id, state=state, label=label))
        await asyncio.sleep(delay_seconds)
