from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job(job_id: UUID, request: Request) -> dict:
    job = request.app.state.persistence.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/events")
async def get_job_events(job_id: UUID, request: Request) -> dict:
    if not request.app.state.persistence.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"events": request.app.state.persistence.list_job_events(job_id)}
