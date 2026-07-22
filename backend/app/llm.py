"""Small, swappable streaming client for Phase 1 chat jobs.

Providers implement :class:`StreamingLLM`. ``create_llm_from_environment`` is the
single seam the routers depend on, so swapping the active provider (or adding a
new one) never touches ``jobs.py`` or the routers.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

PLATT_SYSTEM_PROMPT = (
    "You are Platt, an embodied DevOps agent living inside an engineering team's "
    "dashboard. You help with deployments, pipelines, infrastructure-as-code, and "
    "on-call triage. Be concise, practical, and grounded in what you actually know "
    "from the conversation; never claim to have run a tool or command you were not "
    "given the result of."
)


class LLMConfigurationError(RuntimeError):
    """Raised when a chat job is started without a usable LLM configuration."""


class StreamingLLM(Protocol):
    async def stream_response(self, prompt: str, system_prompt: str | None = None) -> AsyncIterator[str]:
        """Yield text deltas for one tool-free response."""


@dataclass(frozen=True)
class LLMToolCall:
    """One tool call the model asked for, as returned by the provider."""

    id: str
    name: str
    arguments: str  # Raw JSON text; the caller is responsible for parsing it.


@dataclass(frozen=True)
class LLMTurn:
    """One non-streaming turn: either a final answer, or tool calls to run."""

    content: str | None
    tool_calls: tuple[LLMToolCall, ...] = field(default_factory=tuple)


class ToolCallingLLM(Protocol):
    async def complete_turn(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMTurn:
        """Run one non-streaming turn, offering ``tools`` for the model to call."""


class GroqStreamingLLM:
    """OpenAI-compatible streaming client pointed at Groq's chat completions API."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def stream_response(self, prompt: str, system_prompt: str | None = None) -> AsyncIterator[str]:
        # Keep this lazy so local UI and contract tests do not require the SDK/network.
        from openai import AsyncOpenAI

        async with AsyncOpenAI(api_key=self._api_key, base_url=GROQ_BASE_URL) as client:
            stream = await client.chat.completions.create(
                model=self._model,
                stream=True,
                messages=[
                    {"role": "system", "content": system_prompt or PLATT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                text = chunk.choices[0].delta.content
                if text:
                    yield text

    async def complete_turn(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMTurn:
        # Non-streaming: tool-calling turns need the full message before the
        # agent loop can decide whether to run a tool or hand back text.
        from openai import AsyncOpenAI

        async with AsyncOpenAI(api_key=self._api_key, base_url=GROQ_BASE_URL) as client:
            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools or None,
                tool_choice="auto" if tools else None,
            )
        message = response.choices[0].message
        tool_calls = tuple(
            LLMToolCall(id=call.id, name=call.function.name, arguments=call.function.arguments or "{}")
            for call in (message.tool_calls or [])
        )
        return LLMTurn(content=message.content, tool_calls=tool_calls)


class AnthropicStreamingLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def stream_response(self, prompt: str, system_prompt: str | None = None) -> AsyncIterator[str]:
        # Keep this lazy so local UI and contract tests do not require a live provider.
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self._api_key)
        async with client.messages.stream(
            model=self._model,
            max_tokens=1024,
            system=system_prompt or PLATT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text


class UnconfiguredLLM:
    async def stream_response(self, prompt: str, system_prompt: str | None = None) -> AsyncIterator[str]:
        del prompt, system_prompt
        raise LLMConfigurationError(
            "No LLM provider is configured. Set GROQ_API_KEY to stream a live Platt response."
        )
        yield ""  # Makes this method an async generator for the protocol.


def create_llm_from_environment() -> StreamingLLM:
    """Pick a provider from environment variables, preferring Groq.

    Falls back to Anthropic if ``ANTHROPIC_API_KEY`` is set without a Groq key
    (useful for local dev against the previous provider), and to
    :class:`UnconfiguredLLM` when neither is present.
    """

    groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_api_key:
        model = os.environ.get("PLATT_LLM_MODEL", DEFAULT_GROQ_MODEL).strip() or DEFAULT_GROQ_MODEL
        return GroqStreamingLLM(api_key=groq_api_key, model=model)

    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_api_key:
        model = os.environ.get("PLATT_ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL).strip() or DEFAULT_ANTHROPIC_MODEL
        return AnthropicStreamingLLM(api_key=anthropic_api_key, model=model)

    return UnconfiguredLLM()
