import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from app.jobs import stream_chat_job
from app.llm import LLMTurn, LLMToolCall, UnconfiguredLLM
from app.models import AgentStateEvent, ChatDeltaEvent, Event, PlattState
from app.persistence import Persistence
from app.tools.context import ToolContext
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolDefinition, ToolRegistry


class CapturingBus:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)


class StreamingTestLLM:
    async def stream_response(self, prompt: str, system_prompt: str | None = None) -> AsyncIterator[str]:
        assert prompt == "What is deployed?"
        assert system_prompt is None
        yield "The repo "
        yield "deploys Terraform."


class FailingTestLLM:
    async def stream_response(self, prompt: str, system_prompt: str | None = None) -> AsyncIterator[str]:
        del prompt, system_prompt
        raise RuntimeError("provider unavailable")
        yield ""


class ContextTestLLM:
    def __init__(self) -> None:
        self.system_prompt: str | None = None

    async def stream_response(self, prompt: str, system_prompt: str | None = None) -> AsyncIterator[str]:
        assert prompt == "What is deployed?"
        self.system_prompt = system_prompt
        yield "Context received."


def run_job(job_id: UUID, bus: CapturingBus, llm: object) -> None:
    asyncio.run(stream_chat_job(job_id=job_id, bus=bus, llm=llm, prompt="What is deployed?"))  # type: ignore[arg-type]


def test_chat_job_streams_deltas_and_returns_idle() -> None:
    bus = CapturingBus()
    run_job(uuid4(), bus, StreamingTestLLM())

    states = [event.state for event in bus.events if isinstance(event, AgentStateEvent)]
    deltas = [event for event in bus.events if isinstance(event, ChatDeltaEvent)]

    assert states == [PlattState.THINKING, PlattState.TALKING, PlattState.IDLE]
    assert "".join(event.delta for event in deltas) == "The repo deploys Terraform."
    assert deltas[-1].done is True
    assert [event.index for event in deltas] == [0, 1, 2]


def test_chat_job_surfaces_provider_failure_without_sticking_active() -> None:
    bus = CapturingBus()
    run_job(uuid4(), bus, FailingTestLLM())

    states = [event.state for event in bus.events if isinstance(event, AgentStateEvent)]
    deltas = [event for event in bus.events if isinstance(event, ChatDeltaEvent)]

    assert states == [PlattState.THINKING, PlattState.CONCERNED, PlattState.IDLE]
    assert deltas[-1].done is True
    assert "couldn't complete" in "".join(event.delta for event in deltas)


def test_chat_job_passes_a_scoped_system_prompt_to_the_llm() -> None:
    bus = CapturingBus()
    llm = ContextTestLLM()

    asyncio.run(stream_chat_job(job_id=uuid4(), bus=bus, llm=llm, prompt="What is deployed?", system_prompt="Repository inventory: 3 files."))

    assert llm.system_prompt == "Repository inventory: 3 files."


def test_chat_job_explains_missing_configuration_without_exposing_an_exception() -> None:
    bus = CapturingBus()
    run_job(uuid4(), bus, UnconfiguredLLM())

    message = "".join(event.delta for event in bus.events if isinstance(event, ChatDeltaEvent))

    assert "GROQ_API_KEY" in message
    assert "LLMConfigurationError" not in message


ECHO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["value"],
    "properties": {"value": {"type": "string", "maxLength": 32}},
}


async def _echo_handler(arguments: dict, ctx: ToolContext) -> dict:
    del ctx
    return {"echoed": arguments["value"]}


def _echo_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDefinition("echo", "Echo back a string.", ECHO_SCHEMA, _echo_handler))
    return registry


class ScriptedToolCallingLLM:
    """A mocked LLM that plays back pre-scripted turns, exactly like the Groq client would."""

    def __init__(self, turns: list[LLMTurn]) -> None:
        self._turns = list(turns)
        self.seen_messages: list[list[dict]] = []

    async def complete_turn(self, messages: list[dict], tools: list[dict]) -> LLMTurn:
        del tools
        self.seen_messages.append([dict(message) for message in messages])
        return self._turns.pop(0)


def make_persistence(tmp_path) -> Persistence:
    return Persistence(db_path=tmp_path / "platt-jobs-tools-test.db")


def test_tool_loop_executes_a_tool_call_and_streams_the_final_answer(tmp_path) -> None:
    persistence = make_persistence(tmp_path)
    try:
        bus = CapturingBus()
        job_id = uuid4()
        executor = ToolExecutor(_echo_registry(), persistence, {"echo"}, job_id=job_id, event_bus=bus)
        llm = ScriptedToolCallingLLM(
            [
                LLMTurn(content=None, tool_calls=(LLMToolCall(id="call_1", name="echo", arguments='{"value": "ping"}'),)),
                LLMTurn(content="The tool echoed ping.", tool_calls=()),
            ]
        )

        asyncio.run(
            stream_chat_job(
                job_id=job_id,
                bus=bus,
                llm=llm,
                prompt="Echo ping",
                tool_executor=executor,
                tool_names=("echo",),
            )
        )

        states = [event.state for event in bus.events if isinstance(event, AgentStateEvent)]
        deltas = [event for event in bus.events if isinstance(event, ChatDeltaEvent)]

        assert states == [PlattState.THINKING, PlattState.WORKING, PlattState.TALKING, PlattState.IDLE]
        assert "".join(event.delta for event in deltas) == "The tool echoed ping."
        assert deltas[-1].done is True
        assert executor.call_count == 1
        # The tool result is fed back to the model before its final turn.
        assert llm.seen_messages[1][-1] == {"role": "tool", "tool_call_id": "call_1", "content": '{"echoed": "ping"}'}
    finally:
        persistence.close()


def test_tool_loop_stops_and_reports_when_the_cap_is_exceeded(tmp_path) -> None:
    persistence = make_persistence(tmp_path)
    try:
        bus = CapturingBus()
        job_id = uuid4()
        executor = ToolExecutor(_echo_registry(), persistence, {"echo"}, job_id=job_id, event_bus=bus, cap=1)
        llm = ScriptedToolCallingLLM(
            [
                LLMTurn(content=None, tool_calls=(LLMToolCall(id="call_1", name="echo", arguments='{"value": "a"}'),)),
                LLMTurn(content=None, tool_calls=(LLMToolCall(id="call_2", name="echo", arguments='{"value": "b"}'),)),
            ]
        )

        asyncio.run(
            stream_chat_job(
                job_id=job_id,
                bus=bus,
                llm=llm,
                prompt="Echo repeatedly",
                tool_executor=executor,
                tool_names=("echo",),
            )
        )

        states = [event.state for event in bus.events if isinstance(event, AgentStateEvent)]
        deltas = [event for event in bus.events if isinstance(event, ChatDeltaEvent)]

        assert PlattState.CONCERNED in states
        assert states[-1] == PlattState.IDLE
        assert any("tool limit" in event.delta for event in deltas)
        assert executor.call_count == 1
    finally:
        persistence.close()


def test_tool_loop_feeds_invalid_tool_arguments_back_as_an_error_and_continues(tmp_path) -> None:
    persistence = make_persistence(tmp_path)
    try:
        bus = CapturingBus()
        job_id = uuid4()
        executor = ToolExecutor(_echo_registry(), persistence, {"echo"}, job_id=job_id, event_bus=bus)
        llm = ScriptedToolCallingLLM(
            [
                LLMTurn(content=None, tool_calls=(LLMToolCall(id="call_1", name="echo", arguments="not-json"),)),
                LLMTurn(content="Recovered.", tool_calls=()),
            ]
        )

        asyncio.run(
            stream_chat_job(
                job_id=job_id,
                bus=bus,
                llm=llm,
                prompt="Echo something malformed",
                tool_executor=executor,
                tool_names=("echo",),
            )
        )

        deltas = [event for event in bus.events if isinstance(event, ChatDeltaEvent)]
        assert "".join(event.delta for event in deltas) == "Recovered."
        assert executor.call_count == 0
        error_message = llm.seen_messages[1][-1]
        assert error_message["role"] == "tool"
        assert error_message["content"].startswith("error:")
    finally:
        persistence.close()


def test_tool_loop_rejects_a_disallowed_tool_and_feeds_the_rejection_back(tmp_path) -> None:
    persistence = make_persistence(tmp_path)
    try:
        bus = CapturingBus()
        job_id = uuid4()
        executor = ToolExecutor(_echo_registry(), persistence, set(), job_id=job_id, event_bus=bus)
        llm = ScriptedToolCallingLLM(
            [
                LLMTurn(content=None, tool_calls=(LLMToolCall(id="call_1", name="echo", arguments='{"value": "x"}'),)),
                LLMTurn(content="Understood, no tools available.", tool_calls=()),
            ]
        )

        asyncio.run(
            stream_chat_job(
                job_id=job_id,
                bus=bus,
                llm=llm,
                prompt="Try to echo",
                tool_executor=executor,
                tool_names=("echo",),
            )
        )

        deltas = [event for event in bus.events if isinstance(event, ChatDeltaEvent)]
        assert "".join(event.delta for event in deltas) == "Understood, no tools available."
        error_message = llm.seen_messages[1][-1]
        assert "not allowed" in error_message["content"]

        entries = persistence.list_audit_entries(job_id)
        assert any("rejected: not in this job's tool allowlist" in entry["outcome"] for entry in entries)
    finally:
        persistence.close()


def test_no_tool_executor_falls_back_to_plain_streaming() -> None:
    bus = CapturingBus()
    run_job(uuid4(), bus, StreamingTestLLM())

    states = [event.state for event in bus.events if isinstance(event, AgentStateEvent)]
    assert states == [PlattState.THINKING, PlattState.TALKING, PlattState.IDLE]
