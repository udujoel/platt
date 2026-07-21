import asyncio
from dataclasses import dataclass

import pytest

from app.llm import (
    AnthropicStreamingLLM,
    GroqStreamingLLM,
    LLMConfigurationError,
    UnconfiguredLLM,
    create_llm_from_environment,
)


@dataclass
class _FakeDelta:
    content: str | None


@dataclass
class _FakeChoice:
    delta: _FakeDelta


@dataclass
class _FakeChunk:
    choices: list[_FakeChoice]


class _FakeStream:
    def __init__(self, deltas: list[str | None]) -> None:
        self._deltas = deltas

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for delta in self._deltas:
            yield _FakeChunk(choices=[_FakeChoice(delta=_FakeDelta(content=delta))])
        # An empty-choices chunk (e.g. a trailing usage chunk) should be skipped, not crash.
        yield _FakeChunk(choices=[])


class _FakeCompletions:
    def __init__(self, deltas: list[str | None]) -> None:
        self._deltas = deltas
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(self._deltas)


class _FakeChat:
    def __init__(self, deltas: list[str | None]) -> None:
        self.completions = _FakeCompletions(deltas)


class _FakeAsyncOpenAI:
    last_instance: "_FakeAsyncOpenAI | None" = None

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.chat = _FakeChat(["Hello, ", None, "world."])
        self.closed = False
        _FakeAsyncOpenAI.last_instance = self

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> "_FakeAsyncOpenAI":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


class _FakeAsyncOpenAIRaisingOnCreate(_FakeAsyncOpenAI):
    async def __aenter__(self) -> "_FakeAsyncOpenAIRaisingOnCreate":
        self.chat.completions.create = _raise_provider_error
        return self


async def _raise_provider_error(**kwargs):
    raise RuntimeError("provider unavailable")


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PLATT_LLM_MODEL", raising=False)
    monkeypatch.delenv("PLATT_ANTHROPIC_MODEL", raising=False)


async def _collect(llm, prompt="Ping", system_prompt=None) -> str:
    return "".join([delta async for delta in llm.stream_response(prompt, system_prompt=system_prompt)])


def test_groq_streaming_llm_yields_only_non_empty_deltas(monkeypatch):
    monkeypatch.setattr("openai.AsyncOpenAI", _FakeAsyncOpenAI)

    llm = GroqStreamingLLM(api_key="test-key", model="llama-3.3-70b-versatile")
    result = asyncio.run(_collect(llm, prompt="What is deployed?", system_prompt="Be brief."))

    assert result == "Hello, world."
    call = _FakeAsyncOpenAI.last_instance.chat.completions.calls[0]
    assert call["model"] == "llama-3.3-70b-versatile"
    assert call["stream"] is True
    assert call["messages"] == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "What is deployed?"},
    ]


def test_groq_streaming_llm_uses_persona_prompt_when_none_given(monkeypatch):
    monkeypatch.setattr("openai.AsyncOpenAI", _FakeAsyncOpenAI)

    llm = GroqStreamingLLM(api_key="test-key", model="llama-3.3-70b-versatile")
    asyncio.run(_collect(llm))

    call = _FakeAsyncOpenAI.last_instance.chat.completions.calls[0]
    assert call["messages"][0]["role"] == "system"
    assert "Platt" in call["messages"][0]["content"]


def test_groq_streaming_llm_closes_the_client_after_a_successful_stream(monkeypatch):
    monkeypatch.setattr("openai.AsyncOpenAI", _FakeAsyncOpenAI)

    llm = GroqStreamingLLM(api_key="test-key", model="llama-3.3-70b-versatile")
    asyncio.run(_collect(llm))

    assert _FakeAsyncOpenAI.last_instance.closed is True


def test_groq_streaming_llm_closes_the_client_even_if_the_request_fails(monkeypatch):
    monkeypatch.setattr("openai.AsyncOpenAI", _FakeAsyncOpenAIRaisingOnCreate)

    llm = GroqStreamingLLM(api_key="test-key", model="llama-3.3-70b-versatile")

    async def _drain():
        async for _ in llm.stream_response("hi"):
            pass

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(_drain())

    assert _FakeAsyncOpenAI.last_instance.closed is True


def test_create_llm_from_environment_prefers_groq_and_reads_model_override(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setenv("PLATT_LLM_MODEL", "custom-model")

    llm = create_llm_from_environment()

    assert isinstance(llm, GroqStreamingLLM)
    assert llm._model == "custom-model"
    assert llm._api_key == "groq-secret"


def test_create_llm_from_environment_defaults_groq_model(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")

    llm = create_llm_from_environment()

    assert isinstance(llm, GroqStreamingLLM)
    assert llm._model == "llama-3.3-70b-versatile"


def test_create_llm_from_environment_falls_back_to_anthropic_without_groq_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")

    llm = create_llm_from_environment()

    assert isinstance(llm, AnthropicStreamingLLM)


def test_create_llm_from_environment_defaults_anthropic_model_when_override_is_blank(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setenv("PLATT_ANTHROPIC_MODEL", "   ")

    llm = create_llm_from_environment()

    assert isinstance(llm, AnthropicStreamingLLM)
    assert llm._model == "claude-sonnet-4-6"


def test_create_llm_from_environment_returns_unconfigured_without_any_key():
    llm = create_llm_from_environment()

    assert isinstance(llm, UnconfiguredLLM)


def test_unconfigured_llm_raises_configuration_error_mentioning_groq():
    async def _drain():
        async for _ in UnconfiguredLLM().stream_response("hi"):
            pass

    with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY"):
        asyncio.run(_drain())
