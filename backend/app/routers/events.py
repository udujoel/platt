from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import TypeAdapter

from app.models import Event, EventReplayResponse

router = APIRouter(prefix="/events", tags=["events"])
event_adapter = TypeAdapter(Event)


@router.get("/recent", response_model=EventReplayResponse)
def recent_events(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> EventReplayResponse:
    """Expose a bounded, ordered replay window for a reconnecting local client."""
    events = [event_adapter.validate_json(row["payload"]) for row in request.app.state.persistence.list_recent_events(limit)]
    return EventReplayResponse(events=events)
