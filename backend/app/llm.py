"""Small, swappable streaming client for Phase 1 chat jobs."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Protocol


class LLMConfigurationError(RuntimeError):
    """Raised when a chat job is started without a usable LLM configuration."""


class StreamingLLM(Protocol):
    async def stream_response(self, prompt: str) -> AsyncIterator[str]:
        """Yield text deltas for one tool-free response."""


class AnthropicStreamingLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def stream_response(self, prompt: str) -> AsyncIterator[str]:
        # Keep this lazy so local UI and contract tests do not require a live provider.
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self._api_key)
        async with client.messages.stream(
            model=self._model,
            max_tokens=1024,
            system=(
                "You are Platt, an embodied DevOps agent. Be concise, practical, and "
                "do not claim to have executed tools you have not been given."
            ),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text


class UnconfiguredLLM:
    async def stream_response(self, prompt: str) -> AsyncIterator[str]:
        del prompt
        raise LLMConfigurationError(
            "Anthropic is not configured. Set ANTHROPIC_API_KEY to stream a live Platt response."
        )
        yield ""  # Makes this method an async generator for the protocol.


def create_llm_from_environment() -> StreamingLLM:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return UnconfiguredLLM()
    model = os.environ.get("PLATT_ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()
    return AnthropicStreamingLLM(api_key=api_key, model=model)
