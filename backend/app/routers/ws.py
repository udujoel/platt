from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.event_bus import event_bus

router = APIRouter(tags=["events"])


@router.websocket("/ws")
async def websocket_event_bus(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        async for event in event_bus.subscribe():
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        return

