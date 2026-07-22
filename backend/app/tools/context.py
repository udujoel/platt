"""Shared execution context passed from the executor into every tool handler.

Kept dependency-free of the registry/executor modules so all three can import
it without a circular import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.event_bus import EventBus
from app.persistence import Persistence


class ToolExecutionError(RuntimeError):
    """Base class for every error a tool handler or the executor can raise.

    The Groq agent loop (``app.jobs``) catches this one type to turn a failed
    tool call into a ``role: tool`` error message fed back to the model,
    instead of crashing the whole chat job.
    """


@dataclass(frozen=True)
class ToolContext:
    """Everything a handler may need, without granting it more than it asked for."""

    persistence: Persistence
    job_id: UUID | None = None
    event_bus: EventBus | None = None
    resources: dict[str, Any] = field(default_factory=dict)

    def resource(self, name: str) -> Any:
        if name not in self.resources:
            raise ToolExecutionError(f"tool requires unavailable resource: {name}")
        return self.resources[name]
