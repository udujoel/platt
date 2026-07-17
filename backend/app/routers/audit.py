from uuid import UUID

from fastapi import APIRouter, Request

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit_entries(request: Request, job_id: UUID | None = None) -> dict:
    return {"entries": request.app.state.persistence.list_audit_entries(job_id)}
