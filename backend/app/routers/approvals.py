from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.approvals import DEFAULT_APPROVAL_TTL_SECONDS
from app.event_bus import event_bus
from app.models import ApprovalRequiredEvent, ApprovalResultEvent

router = APIRouter(prefix="/approvals", tags=["approvals"])


class CreateApprovalRequest(BaseModel):
    job_id: UUID
    plan_hash: str = Field(min_length=1, max_length=256)
    commit_sha: str = Field(min_length=1, max_length=256)
    scope: str = Field(min_length=1, max_length=256)
    summary: str = Field(default="Approval requested", max_length=512)


class CreateApprovalResponse(BaseModel):
    id: UUID
    job_id: UUID
    plan_hash: str
    commit_sha: str
    scope: str
    status: Literal["pending"] = "pending"


class DecideApprovalRequest(BaseModel):
    approver: str = Field(min_length=1, max_length=256)
    decision: Literal["approved", "rejected"]
    ttl_seconds: int = Field(default=DEFAULT_APPROVAL_TTL_SECONDS, gt=0)


@router.post("", response_model=CreateApprovalResponse, status_code=status.HTTP_201_CREATED)
async def create_approval(request: Request, payload: CreateApprovalRequest) -> CreateApprovalResponse:
    """Bind an approval request to the exact job, plan hash, and commit that need it."""
    approval_id = uuid4()
    persistence = request.app.state.persistence
    persistence.create_approval(
        approval_id=approval_id,
        job_id=payload.job_id,
        plan_hash=payload.plan_hash,
        commit_sha=payload.commit_sha,
        scope=payload.scope,
    )
    await event_bus.publish(
        ApprovalRequiredEvent(job_id=payload.job_id, approval_id=approval_id, summary=payload.summary)
    )
    return CreateApprovalResponse(
        id=approval_id,
        job_id=payload.job_id,
        plan_hash=payload.plan_hash,
        commit_sha=payload.commit_sha,
        scope=payload.scope,
    )


@router.post("/{approval_id}/decide")
async def decide_approval(request: Request, approval_id: UUID, payload: DecideApprovalRequest) -> dict:
    """Record a one-time approve/reject decision; a second decide on the same id fails."""
    persistence = request.app.state.persistence
    existing = persistence.get_approval(approval_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="approval not found")

    expires_at = None
    if payload.decision == "approved":
        expires_at = datetime.utcnow() + timedelta(seconds=payload.ttl_seconds)

    rows_affected = persistence.decide_approval(
        approval_id=approval_id,
        approver=payload.approver,
        status=payload.decision,
        expires_at=expires_at,
    )
    if rows_affected == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"approval already decided (status={existing['status']})",
        )

    record = persistence.get_approval(approval_id)
    await event_bus.publish(
        ApprovalResultEvent(
            job_id=UUID(record["job_id"]),
            approval_id=approval_id,
            approved=payload.decision == "approved",
        )
    )
    return record


@router.get("")
async def list_approvals(request: Request, job_id: UUID | None = None) -> dict:
    return {"approvals": request.app.state.persistence.list_approvals(job_id)}


@router.get("/{approval_id}")
async def get_approval(request: Request, approval_id: UUID) -> dict:
    record = request.app.state.persistence.get_approval(approval_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="approval not found")
    return record
