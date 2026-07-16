from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class PlattState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    WORKING = "working"
    TALKING = "talking"
    AWAITING_APPROVAL = "awaiting_approval"
    CELEBRATING = "celebrating"
    CONCERNED = "concerned"


class EventType(StrEnum):
    AGENT_STATE = "agent_state"
    CHAT_DELTA = "chat_delta"
    JOB_CREATED = "job_created"
    WORK_ITEM_MOVED = "work_item_moved"
    PIPELINE_UPDATE = "pipeline_update"
    PLAN_READY = "plan_ready"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_RESULT = "approval_result"
    APPLY_RESULT = "apply_result"
    AUDIT_ENTRY = "audit_entry"
    DASHBOARD_REFRESH = "dashboard_refresh"


class EventBase(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    type: EventType
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobEvent(EventBase):
    job_id: UUID


class AgentStateEvent(JobEvent):
    type: Literal[EventType.AGENT_STATE] = EventType.AGENT_STATE
    state: PlattState
    label: str


class ChatDeltaEvent(JobEvent):
    type: Literal[EventType.CHAT_DELTA] = EventType.CHAT_DELTA
    delta: str
    index: int = Field(ge=0)
    done: bool = False


class JobCreatedEvent(JobEvent):
    type: Literal[EventType.JOB_CREATED] = EventType.JOB_CREATED
    prompt: str


class WorkItemMovedEvent(JobEvent):
    type: Literal[EventType.WORK_ITEM_MOVED] = EventType.WORK_ITEM_MOVED
    work_item_id: str
    title: str
    from_state: str
    to_state: str


class PipelineUpdateEvent(JobEvent):
    type: Literal[EventType.PIPELINE_UPDATE] = EventType.PIPELINE_UPDATE
    pipeline_name: str
    status: str
    url: str | None = None


class PlanReadyEvent(JobEvent):
    type: Literal[EventType.PLAN_READY] = EventType.PLAN_READY
    summary: str
    has_blocking_changes: bool = False


class ApprovalRequiredEvent(JobEvent):
    type: Literal[EventType.APPROVAL_REQUIRED] = EventType.APPROVAL_REQUIRED
    approval_id: UUID
    summary: str


class ApprovalResultEvent(JobEvent):
    type: Literal[EventType.APPROVAL_RESULT] = EventType.APPROVAL_RESULT
    approval_id: UUID
    approved: bool


class ApplyResultEvent(JobEvent):
    type: Literal[EventType.APPLY_RESULT] = EventType.APPLY_RESULT
    success: bool
    summary: str


class AuditEntryEvent(JobEvent):
    type: Literal[EventType.AUDIT_ENTRY] = EventType.AUDIT_ENTRY
    tool: str
    action: str
    outcome: str


class DashboardRefreshEvent(EventBase):
    type: Literal[EventType.DASHBOARD_REFRESH] = EventType.DASHBOARD_REFRESH
    metrics: dict[str, int | float | str]


Event = Annotated[
    Union[
        AgentStateEvent,
        ChatDeltaEvent,
        JobCreatedEvent,
        WorkItemMovedEvent,
        PipelineUpdateEvent,
        PlanReadyEvent,
        ApprovalRequiredEvent,
        ApprovalResultEvent,
        ApplyResultEvent,
        AuditEntryEvent,
        DashboardRefreshEvent,
    ],
    Field(discriminator="type"),
]


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    job_id: UUID
    status: Literal["accepted"] = "accepted"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"

