"""Validates, allowlists, audits, and caps every tool call the agent loop makes.

This is the single choke point PRD §7.4/§8 requires: a tool call that isn't in
this job's allowlist, doesn't match its schema, or would exceed the per-job
cap never reaches a handler, and every attempt — allowed or not — leaves
exactly one redacted audit entry.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from app.event_bus import EventBus
from app.models import AuditEntryEvent
from app.persistence import Persistence
from app.tools.context import ToolContext, ToolExecutionError
from app.tools.registry import ToolRegistry
from app.tools.schema import SchemaValidationError, validate_arguments

DEFAULT_TOOL_CALL_CAP = 40
AUDIT_TOOL_NAME = "agent"
_MAX_SUMMARY_CHARS = 512
_REDACTED_KEYS = {"pat", "token", "password", "authorization", "secret"}
_MAX_VALUE_CHARS = 200


class ToolNotAllowedError(ToolExecutionError):
    def __init__(self, name: str) -> None:
        super().__init__(f"tool not allowed for this job: {name}")
        self.name = name


class ToolNotFoundError(ToolExecutionError):
    def __init__(self, name: str) -> None:
        super().__init__(f"unknown tool: {name}")
        self.name = name


class ToolValidationError(ToolExecutionError):
    def __init__(self, name: str, message: str) -> None:
        super().__init__(f"invalid arguments for {name}: {message}")
        self.name = name


class ToolCapExceededError(ToolExecutionError):
    def __init__(self, cap: int) -> None:
        super().__init__(f"tool call cap of {cap} exceeded")
        self.cap = cap


def _redact_arguments(arguments: dict[str, Any]) -> str:
    parts = []
    for key, value in arguments.items():
        if key.lower() in _REDACTED_KEYS:
            parts.append(f"{key}=<redacted>")
            continue
        text = str(value)
        if len(text) > _MAX_VALUE_CHARS:
            text = text[:_MAX_VALUE_CHARS] + "...(truncated)"
        parts.append(f"{key}={text}")
    return ", ".join(parts)


def _summarize_result(result: Any) -> str:
    text = str(result)
    if len(text) > _MAX_SUMMARY_CHARS:
        text = text[:_MAX_SUMMARY_CHARS] + "...(truncated)"
    return text


class ToolExecutor:
    """Runs one job's tool calls against a fixed allowlist and cap.

    One instance is scoped to a single job: it owns the running call count the
    cap check compares against, so it must never be shared across jobs.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        persistence: Persistence,
        allowlist: Iterable[str],
        *,
        job_id: UUID | None = None,
        event_bus: EventBus | None = None,
        cap: int = DEFAULT_TOOL_CALL_CAP,
        resources: dict[str, Any] | None = None,
    ) -> None:
        if cap < 1:
            raise ValueError("cap must be positive")
        self.registry = registry
        self._persistence = persistence
        self._allowlist = frozenset(allowlist)
        self._job_id = job_id
        self._event_bus = event_bus
        self._cap = cap
        self._resources = dict(resources or {})
        self._calls = 0

    @property
    def call_count(self) -> int:
        return self._calls

    @property
    def cap(self) -> int:
        return self._cap

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._calls >= self._cap:
            await self._audit(name, arguments, ok=False, summary=f"rejected: tool call cap of {self._cap} reached")
            raise ToolCapExceededError(self._cap)

        if name not in self._allowlist:
            await self._audit(name, arguments, ok=False, summary="rejected: not in this job's tool allowlist")
            raise ToolNotAllowedError(name)

        tool = self.registry.get(name)
        if tool is None:
            await self._audit(name, arguments, ok=False, summary="rejected: unknown tool")
            raise ToolNotFoundError(name)

        try:
            validate_arguments(arguments, tool.parameters)
        except SchemaValidationError as error:
            await self._audit(name, arguments, ok=False, summary=f"rejected: {error}")
            raise ToolValidationError(name, str(error)) from error

        self._calls += 1
        context = ToolContext(
            persistence=self._persistence,
            job_id=self._job_id,
            event_bus=self._event_bus,
            resources=self._resources,
        )
        try:
            result = await tool.handler(arguments, context)
        except ToolExecutionError as error:
            await self._audit(name, arguments, ok=False, summary=f"error: {error}")
            raise
        except Exception as error:
            await self._audit(name, arguments, ok=False, summary=f"error: {error}")
            raise ToolExecutionError(str(error)) from error

        await self._audit(name, arguments, ok=True, summary=_summarize_result(result))
        return result

    async def _audit(self, name: str, arguments: dict[str, Any], *, ok: bool, summary: str) -> None:
        status = "succeeded" if ok else "error"
        outcome = f"{status} | args: {_redact_arguments(arguments)} | result: {summary}"[:_MAX_SUMMARY_CHARS]
        self._persistence.record_audit_entry(self._job_id, tool=AUDIT_TOOL_NAME, action=name, outcome=outcome)
        if self._event_bus is not None and self._job_id is not None:
            await self._event_bus.publish(
                AuditEntryEvent(
                    job_id=self._job_id,
                    tool=AUDIT_TOOL_NAME,
                    action=name,
                    outcome=status,
                    summary=outcome[:512],
                )
            )
