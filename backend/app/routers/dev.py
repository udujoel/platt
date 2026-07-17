import asyncio
from uuid import uuid4

from fastapi import APIRouter

from app.event_bus import event_bus
from app.jobs import stream_dev_state_cycle
from app.models import DevCycleResponse

router = APIRouter(prefix="/dev", tags=["development"])


@router.post("/state-cycle", response_model=DevCycleResponse, status_code=202)
async def state_cycle() -> DevCycleResponse:
    job_id = uuid4()
    asyncio.create_task(stream_dev_state_cycle(job_id=job_id, bus=event_bus))
    return DevCycleResponse(job_id=job_id)
