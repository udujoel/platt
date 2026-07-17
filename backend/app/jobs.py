import asyncio
from uuid import UUID

from app.event_bus import EventBus
from app.llm import LLMConfigurationError, StreamingLLM
from app.models import AgentStateEvent, ChatDeltaEvent, PlattState


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


async def stream_chat_job(job_id: UUID, bus: EventBus, llm: StreamingLLM, prompt: str) -> None:
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Planning response"))
    next_index = 0
    response_started = False
    try:
        async for delta in llm.stream_response(prompt):
            if not delta:
                continue
            if not response_started:
                response_started = True
                await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.TALKING, label="Streaming response"))
            await bus.publish(ChatDeltaEvent(job_id=job_id, delta=delta, index=next_index))
            next_index += 1
        if not response_started:
            raise RuntimeError("The language model returned an empty response.")
    except LLMConfigurationError:
        await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.CONCERNED, label="Chat provider unavailable"))
        await bus.publish(ChatDeltaEvent(job_id=job_id, delta="Anthropic is not configured. Set ANTHROPIC_API_KEY to stream a live Platt response.", index=next_index))
        next_index += 1
    except Exception:
        await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.CONCERNED, label="Chat provider failed"))
        await bus.publish(ChatDeltaEvent(job_id=job_id, delta="The chat provider couldn't complete that response. Please try again.", index=next_index))
        next_index += 1
    finally:
        await bus.publish(ChatDeltaEvent(job_id=job_id, delta="", index=next_index, done=True))
        await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.IDLE, label="Ready"))


async def stream_dev_state_cycle(job_id: UUID, bus: EventBus, delay_seconds: float = 0.35) -> None:
    for state, label in DEV_STATE_SEQUENCE:
        await bus.publish(AgentStateEvent(job_id=job_id, state=state, label=label))
        await asyncio.sleep(delay_seconds)
