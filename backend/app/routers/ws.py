import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.event_bus import event_bus

router = APIRouter(tags=["events"])


@router.websocket("/ws")
async def websocket_event_bus(websocket: WebSocket) -> None:
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
