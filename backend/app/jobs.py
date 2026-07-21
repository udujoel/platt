import asyncio
import json
from typing import Any
from uuid import UUID

from app.event_bus import EventBus
from app.llm import LLMConfigurationError, PLATT_SYSTEM_PROMPT, StreamingLLM
from app.models import AgentStateEvent, ChatDeltaEvent, PlattState
from app.tools.executor import ToolCapExceededError, ToolExecutionError, ToolExecutor


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

# One more turn than the default tool call cap: the cap itself is the real
# stop condition, this is only a backstop against a misbehaving provider that
# never emits a final answer.
MAX_TOOL_LOOP_TURNS = 64


async def stream_chat_job(
    job_id: UUID,
    bus: EventBus,
    llm: StreamingLLM,
    prompt: str,
    system_prompt: str | None = None,
    tool_executor: ToolExecutor | None = None,
    tool_names: tuple[str, ...] = (),
) -> None:
    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Planning response"))
    if tool_executor is not None and tool_names and hasattr(llm, "complete_turn"):
        await _run_tool_loop(job_id, bus, llm, prompt, system_prompt, tool_executor, tool_names)
        return
    await _run_plain_stream(job_id, bus, llm, prompt, system_prompt)


async def _run_plain_stream(
    job_id: UUID,
    bus: EventBus,
    llm: StreamingLLM,
    prompt: str,
    system_prompt: str | None,
) -> None:
    next_index = 0
    response_started = False
    try:
        async for delta in llm.stream_response(prompt, system_prompt=system_prompt):
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
        await bus.publish(ChatDeltaEvent(job_id=job_id, delta="No LLM provider is configured. Set GROQ_API_KEY to stream a live Platt response.", index=next_index))
        next_index += 1
    except Exception:
        await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.CONCERNED, label="Chat provider failed"))
        await bus.publish(ChatDeltaEvent(job_id=job_id, delta="The chat provider couldn't complete that response. Please try again.", index=next_index))
        next_index += 1
    finally:
        await bus.publish(ChatDeltaEvent(job_id=job_id, delta="", index=next_index, done=True))
        await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.IDLE, label="Ready"))


def _tool_result_message(call_id: str, content: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


async def _run_tool_loop(
    job_id: UUID,
    bus: EventBus,
    llm: Any,
    prompt: str,
    system_prompt: str | None,
    tool_executor: ToolExecutor,
    tool_names: tuple[str, ...],
) -> None:
    next_index = 0
    try:
        tool_schemas = tool_executor.registry.schemas_for(tool_names)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt or PLATT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        for _ in range(MAX_TOOL_LOOP_TURNS):
            turn = await llm.complete_turn(messages, tool_schemas)

            if not turn.tool_calls:
                if not turn.content:
                    raise RuntimeError("The language model returned an empty response.")
                await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.TALKING, label="Streaming response"))
                await bus.publish(ChatDeltaEvent(job_id=job_id, delta=turn.content, index=next_index))
                next_index += 1
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": turn.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": call.arguments},
                        }
                        for call in turn.tool_calls
                    ],
                }
            )
            await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.WORKING, label="Tool execution in flight"))

            for call in turn.tool_calls:
                try:
                    arguments = json.loads(call.arguments) if call.arguments else {}
                    if not isinstance(arguments, dict):
                        raise ValueError("tool arguments must be a JSON object")
                except (json.JSONDecodeError, ValueError) as error:
                    messages.append(_tool_result_message(call.id, f"error: {error}"))
                    continue

                try:
                    result = await tool_executor.execute(call.name, arguments)
                except ToolCapExceededError:
                    await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.CONCERNED, label="Tool call cap exceeded"))
                    await bus.publish(
                        ChatDeltaEvent(
                            job_id=job_id,
                            delta=f"Stopping: reached this job's {tool_executor.cap}-call tool limit.",
                            index=next_index,
                        )
                    )
                    next_index += 1
                    return
                except ToolExecutionError as error:
                    messages.append(_tool_result_message(call.id, f"error: {error}"))
                    continue

                messages.append(_tool_result_message(call.id, json.dumps(result, default=str)))
        raise RuntimeError("The agent did not reach a final answer within its turn budget.")
    except LLMConfigurationError:
        await bus.publish(AgentStateEvent(job_id=job_id, state=PlattState.CONCERNED, label="Chat provider unavailable"))
        await bus.publish(ChatDeltaEvent(job_id=job_id, delta="No LLM provider is configured. Set GROQ_API_KEY to stream a live Platt response.", index=next_index))
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
