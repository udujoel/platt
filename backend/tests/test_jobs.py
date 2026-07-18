import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from app.jobs import stream_chat_job
from app.llm import UnconfiguredLLM
from app.models import AgentStateEvent, ChatDeltaEvent, Event, PlattState


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

    assert "ANTHROPIC_API_KEY" in message
    assert "LLMConfigurationError" not in message
