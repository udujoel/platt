from uuid import uuid4

from fastapi import APIRouter, Request

from app.background_tasks import create_background_task
from app.event_bus import event_bus
from app.jobs import stream_dev_state_cycle
from app.models import DevCycleResponse

router = APIRouter(prefix="/dev", tags=["development"])


@router.post("/state-cycle", response_model=DevCycleResponse, status_code=202)
async def state_cycle(request: Request) -> DevCycleResponse:
    job_id = uuid4()
    create_background_task(request.app, stream_dev_state_cycle(job_id=job_id, bus=event_bus))
    return DevCycleResponse(job_id=job_id)
