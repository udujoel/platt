import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.status import WS_1008_POLICY_VIOLATION

from app.event_bus import event_bus

router = APIRouter(tags=["events"])


@router.websocket("/ws")
async def websocket_event_bus(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    allowed_origin_pattern = websocket.app.state.allowed_origin_pattern
    if origin is None or allowed_origin_pattern.fullmatch(origin) is None:
        # Accepting then closing gives browser clients a consistent policy
        # violation code while still denying any subscription or event data.
        await websocket.accept()
        await websocket.close(code=WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        async for event in event_bus.subscribe():
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except (WebSocketDisconnect, RuntimeError):
                # A client transport can close after the event is dequeued but
                # before the ASGI server performs the send. Treat that race as
                # a normal disconnect so the subscription is cleaned up.
                return
    except asyncio.CancelledError:
        raise
    except WebSocketDisconnect:
        return
